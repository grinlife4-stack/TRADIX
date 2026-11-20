"""Deterministic, bounded, self-verifying Bridge source package creation."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from .manifest import BridgeManifestError, _safe_relative_path, load_manifest, read_regular_file, resolve_package_files, validate_manifest_data

PACKAGE_MANIFEST = "BRIDEX_PACKAGE_MANIFEST.json"
PACKAGE_FORMAT = "BRIDEX-PACKAGE-0.1"
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_PACKAGE_BYTES = 256 * 1024 * 1024
MAX_PACKAGE_ENTRIES = 514


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    return info


def build_package(root: str | Path, output: str | Path, *, max_package_bytes: int = MAX_PACKAGE_BYTES) -> dict[str, Any]:
    root_path, manifest = load_manifest(root)
    requested_output = Path(output).expanduser().absolute()
    if not requested_output.name or requested_output.name in {".", ".."}:
        raise BridgeManifestError("package_output_path_invalid")
    try:
        requested_output.relative_to(root_path)
    except ValueError:
        pass
    else:
        raise BridgeManifestError("package_output_must_be_outside_bridge_root")
    requested_output.parent.mkdir(parents=True, exist_ok=True)
    output_parent = requested_output.parent.resolve(strict=True)
    output_path = output_parent / requested_output.name
    try:
        output_path.relative_to(root_path)
    except ValueError:
        pass
    else:
        raise BridgeManifestError("package_output_must_be_outside_bridge_root")
    if output_path.exists() or output_path.is_symlink():
        raise BridgeManifestError("package_output_already_exists")
    if not isinstance(max_package_bytes, int) or not 1 <= max_package_bytes <= MAX_PACKAGE_BYTES:
        raise ValueError("max_package_bytes_must_be_between_1_and_default_limit")

    source_files = [("bridge.json", root_path / "bridge.json")] + resolve_package_files(root_path, manifest)
    entries: list[tuple[str, bytes]] = []
    total_bytes = 0
    for name, _path in source_files:
        data = read_regular_file(root_path, _safe_relative_path(name, allow_reserved=True), max_bytes=MAX_FILE_BYTES)
        if len(data) > MAX_FILE_BYTES:
            raise BridgeManifestError("package_file_size_limit_exceeded")
        total_bytes += len(data)
        if total_bytes > max_package_bytes:
            raise BridgeManifestError("package_total_size_limit_exceeded")
        entries.append((name, data))

    file_records = [
        {"path": name, "size_bytes": len(data), "sha256": _sha256(data)}
        for name, data in sorted(entries, key=lambda item: item[0])
    ]
    package_manifest = {
        "format": PACKAGE_FORMAT,
        "bridge_id": manifest["bridge_id"],
        "version": manifest["version"],
        "file_count": len(file_records),
        "total_bytes": total_bytes,
        "files": file_records,
    }
    package_manifest_bytes = (json.dumps(package_manifest, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=".bridex-package-", suffix=".tmp", dir=output_path.parent)
    os.close(fd)
    temporary_path = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, data in sorted(entries, key=lambda item: item[0]):
                archive.writestr(_zip_info(name), data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
            archive.writestr(_zip_info(PACKAGE_MANIFEST), package_manifest_bytes, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        try:
            os.link(temporary_path, output_path)
        except FileExistsError as exc:
            raise BridgeManifestError("package_output_already_exists") from exc
        temporary_path.unlink(missing_ok=True)
    finally:
        temporary_path.unlink(missing_ok=True)

    return {
        "package_path": str(output_path),
        "bridge_id": manifest["bridge_id"],
        "version": manifest["version"],
        "file_count": len(file_records),
        "total_bytes": total_bytes,
        "sha256": _sha256(output_path.read_bytes()),
    }


def verify_package(package_path: str | Path, *, max_package_bytes: int = MAX_PACKAGE_BYTES) -> dict[str, Any]:
    path = Path(package_path)
    if not path.is_file() or path.is_symlink():
        raise BridgeManifestError("package_file_unavailable")
    if not isinstance(max_package_bytes, int) or not 1 <= max_package_bytes <= MAX_PACKAGE_BYTES:
        raise ValueError("max_package_bytes_must_be_between_1_and_default_limit")
    try:
        archive_size = path.stat().st_size
    except OSError as exc:
        raise BridgeManifestError("package_file_unavailable") from exc
    if archive_size > max_package_bytes + 4 * 1024 * 1024:
        raise BridgeManifestError("package_archive_size_limit_exceeded")
    try:
        archive = zipfile.ZipFile(path, "r")
    except (OSError, zipfile.BadZipFile) as exc:
        raise BridgeManifestError("package_archive_invalid") from exc

    if not isinstance(max_package_bytes, int) or max_package_bytes < 1:
        raise ValueError("max_package_bytes_must_be_positive")

    with archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise BridgeManifestError("package_duplicate_entries_rejected")
        if len(infos) > MAX_PACKAGE_ENTRIES:
            raise BridgeManifestError("package_entry_count_limit_exceeded")
        declared_uncompressed = sum(info.file_size for info in infos)
        if declared_uncompressed > max_package_bytes:
            raise BridgeManifestError("package_total_size_limit_exceeded")
        for info in infos:
            _safe_relative_path(info.filename, allow_reserved=True)
            if info.flag_bits & 0x1:
                raise BridgeManifestError("package_encrypted_entry_rejected")
            if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                raise BridgeManifestError("package_compression_method_unsupported")
            mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
                raise BridgeManifestError("package_non_regular_entry_rejected")
            if info.file_size > MAX_FILE_BYTES:
                raise BridgeManifestError("package_file_size_limit_exceeded")
            if info.filename in {"bridge.json", PACKAGE_MANIFEST} and info.file_size > 1_048_576:
                raise BridgeManifestError("package_metadata_size_limit_exceeded")
            if info.file_size < 0:
                raise BridgeManifestError("package_file_size_invalid")
        if PACKAGE_MANIFEST not in names or "bridge.json" not in names:
            raise BridgeManifestError("package_required_manifest_missing")

        try:
            bridge_manifest = json.loads(archive.read("bridge.json").decode("utf-8"))
            validate_manifest_data(bridge_manifest)
            package_manifest = json.loads(archive.read(PACKAGE_MANIFEST).decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError, KeyError) as exc:
            raise BridgeManifestError("package_manifest_invalid") from exc

        if not isinstance(package_manifest, dict) or set(package_manifest) != {
            "format", "bridge_id", "version", "file_count", "total_bytes", "files"
        } or package_manifest.get("format") != PACKAGE_FORMAT:
            raise BridgeManifestError("package_format_unsupported")
        if package_manifest.get("bridge_id") != bridge_manifest["bridge_id"] or package_manifest.get("version") != bridge_manifest["version"]:
            raise BridgeManifestError("package_identity_mismatch")
        records = package_manifest.get("files")
        if not isinstance(records, list) or len(records) > MAX_PACKAGE_ENTRIES - 1:
            raise BridgeManifestError("package_file_manifest_invalid")
        declared_names = {"bridge.json"} | set(bridge_manifest["package_files"])
        expected_names = {"bridge.json"}
        total_bytes = 0
        seen: set[str] = set()
        for record in records:
            if not isinstance(record, dict) or set(record) != {"path", "size_bytes", "sha256"}:
                raise BridgeManifestError("package_file_record_invalid")
            name = _safe_relative_path(record["path"], allow_reserved=True).as_posix()
            if name in seen:
                raise BridgeManifestError("package_duplicate_file_record")
            seen.add(name)
            if type(record["size_bytes"]) is not int or record["size_bytes"] < 0:
                raise BridgeManifestError("package_file_size_invalid")
            if not isinstance(record["sha256"], str) or len(record["sha256"]) != 64 or any(ch not in "0123456789abcdef" for ch in record["sha256"]):
                raise BridgeManifestError("package_file_hash_invalid")
            expected_names.add(name)
            data = archive.read(name) if name in names else None
            if data is None:
                raise BridgeManifestError("package_file_missing")
            if len(data) != record["size_bytes"] or _sha256(data) != record["sha256"]:
                raise BridgeManifestError("package_file_integrity_failed")
            total_bytes += len(data)
        if seen != declared_names or expected_names != declared_names:
            raise BridgeManifestError("package_manifest_file_set_mismatch")
        if expected_names | {PACKAGE_MANIFEST} != set(names):
            raise BridgeManifestError("package_unlisted_entry_rejected")
        bridge_bytes = archive.read("bridge.json")
        if not any(record.get("path") == "bridge.json" for record in records):
            total_bytes += len(bridge_bytes)
        if total_bytes != package_manifest.get("total_bytes"):
            raise BridgeManifestError("package_total_size_mismatch")
        if type(package_manifest.get("file_count")) is not int or package_manifest.get("file_count") != len(records):
            raise BridgeManifestError("package_file_count_mismatch")
        if type(package_manifest.get("total_bytes")) is not int:
            raise BridgeManifestError("package_total_size_mismatch")
        if total_bytes > max_package_bytes:
            raise BridgeManifestError("package_total_size_limit_exceeded")

    return {
        "valid": True,
        "bridge_id": bridge_manifest["bridge_id"],
        "version": bridge_manifest["version"],
        "file_count": package_manifest["file_count"],
        "total_bytes": total_bytes,
        "sha256": _sha256(path.read_bytes()),
    }
