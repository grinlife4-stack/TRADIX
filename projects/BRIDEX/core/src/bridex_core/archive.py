"""Deterministic Bridge package export and safe restore."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from .layout import verify_package
from .manifest import ManifestValidationError


MAX_ARCHIVE_ENTRIES = 10_000
MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
_FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def export_package(package_root: str | Path, archive_path: str | Path) -> dict[str, Any]:
    """Create a deterministic ZIP export from a verified package directory."""
    root = Path(package_root).resolve(strict=True)
    verify_package(root)
    destination = Path(archive_path).resolve()
    try:
        destination.relative_to(root)
    except ValueError:
        pass
    else:
        raise ManifestValidationError("archive output must be outside the package directory")
    if destination.exists():
        raise ManifestValidationError("archive output already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)

    files = sorted(path for path in root.rglob("*") if path.is_file())
    if len(files) > MAX_ARCHIVE_ENTRIES:
        raise ManifestValidationError("package contains too many files")
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            if path.is_symlink():
                raise ManifestValidationError("package export rejects symlink files")
            resolved = path.resolve(strict=True)
            try:
                resolved.relative_to(root)
            except ValueError as exc:
                raise ManifestValidationError("package export rejects paths outside package root") from exc
            relative = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(relative, date_time=_FIXED_ZIP_TIME)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    return {"archive": destination.name, "sha256": digest, "files": len(files), "bytes": destination.stat().st_size}


def restore_package(archive_path: str | Path, destination: str | Path) -> dict[str, Any]:
    """Safely restore a ZIP export into a new directory and verify its manifest/artifact."""
    archive_file = Path(archive_path).resolve(strict=True)
    target = Path(destination).resolve()
    if target.exists():
        raise ManifestValidationError("restore destination already exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging_parent = Path(tempfile.mkdtemp(prefix=".bridex-restore-", dir=target.parent))
    staging = staging_parent / "package"
    staging.mkdir()
    try:
        with zipfile.ZipFile(archive_file, "r") as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ARCHIVE_ENTRIES:
                raise ManifestValidationError("archive contains too many entries")
            total = sum(info.file_size for info in infos)
            if total > MAX_UNCOMPRESSED_BYTES:
                raise ManifestValidationError("archive exceeds uncompressed size limit")
            seen: set[str] = set()
            for info in infos:
                name = info.filename
                if not name or "\\" in name:
                    raise ManifestValidationError("archive contains an invalid path")
                relative = PurePosixPath(name)
                if relative.is_absolute() or any(part in ("", ".", "..") for part in relative.parts):
                    raise ManifestValidationError("archive path traversal is forbidden")
                normalized = relative.as_posix().rstrip("/")
                if normalized in seen:
                    raise ManifestValidationError("archive contains duplicate paths")
                seen.add(normalized)
                mode = (info.external_attr >> 16) & 0xFFFF
                kind = stat.S_IFMT(mode)
                if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
                    raise ManifestValidationError("archive contains a symlink or special file")
                if info.flag_bits & 0x1:
                    raise ManifestValidationError("encrypted archive entries are not supported")
                output = staging.joinpath(*relative.parts)
                try:
                    output.resolve().relative_to(staging.resolve())
                except ValueError as exc:
                    raise ManifestValidationError("archive entry escapes restore directory") from exc
                if info.is_dir():
                    output.mkdir(parents=True, exist_ok=True)
                else:
                    output.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info, "r") as source, output.open("xb") as sink:
                        shutil.copyfileobj(source, sink)
        report = verify_package(staging)
        os.replace(staging, target)
        return {**report, "restored_to": str(target)}
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise ManifestValidationError("archive could not be safely restored") from exc
    finally:
        shutil.rmtree(staging_parent, ignore_errors=True)
