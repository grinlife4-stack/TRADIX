"""Strict validation for independent Bridge manifests and package file sets."""

from __future__ import annotations

import json
import os
import re
import stat
import uuid
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


_SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".p7b", ".p7c", ".jks", ".keystore"}
_FORBIDDEN_SEGMENTS = {
    ".git", ".ssh", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "secrets", "credentials",
    "dist", "build",
}
_RESERVED_NAMES = {"bridge.json", "bridex_package_manifest.json"}
_SCHEMA = json.loads(
    files("bridex_engine").joinpath("schemas").joinpath("bridge-manifest.schema.json").read_text(encoding="utf-8")
)
_VALIDATOR = Draft202012Validator(_SCHEMA, format_checker=FormatChecker())


class BridgeManifestError(ValueError):
    """Raised when a Bridge manifest or package file set is unsafe or invalid."""


def _safe_relative_path(value: Any, *, allow_reserved: bool = False) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise BridgeManifestError("package_path_invalid")
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise BridgeManifestError("package_path_must_be_relative")
    raw_parts = value.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        raise BridgeManifestError("package_path_traversal_rejected")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part.lower() in _FORBIDDEN_SEGMENTS for part in path.parts):
        raise BridgeManifestError("package_path_forbidden")
    if not allow_reserved and path.name.lower() in _RESERVED_NAMES:
        raise BridgeManifestError("package_path_reserved")
    if path.suffix.lower() in _SECRET_SUFFIXES or path.name.lower().startswith((".env", "id_rsa", "id_ed25519")):
        raise BridgeManifestError("package_secret_path_rejected")
    if any(token in path.name.lower() for token in ("secret", "credential", "private-key", "access-token")):
        raise BridgeManifestError("package_secret_path_rejected")
    return path


def validate_manifest_data(manifest: Any) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise BridgeManifestError("manifest_must_be_object")
    errors = sorted(_VALIDATOR.iter_errors(manifest), key=lambda item: list(item.path))
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.path) or "$"
        raise BridgeManifestError(f"manifest_schema_invalid:{location}:{first.validator}")
    try:
        uuid.UUID(manifest["bridge_id"][9:])
    except (ValueError, TypeError, AttributeError) as exc:
        raise BridgeManifestError("bridge_id_must_contain_uuid") from exc

    capability_ids = [item["capability_id"] for item in manifest["capabilities"]]
    if len(set(capability_ids)) != len(capability_ids):
        raise BridgeManifestError("capability_ids_must_be_unique")
    for value in manifest["package_files"]:
        _safe_relative_path(value)
    return manifest


def _resolve_regular_file(root: Path, relative: PurePosixPath) -> Path:
    current = root
    for part in relative.parts:
        current = current / part
        try:
            if current.is_symlink():
                raise BridgeManifestError("package_symlink_rejected")
        except OSError as exc:
            raise BridgeManifestError("package_path_unavailable") from exc
    try:
        resolved = current.resolve(strict=True)
        resolved.relative_to(root)
        metadata = resolved.stat()
    except (OSError, ValueError) as exc:
        raise BridgeManifestError("package_file_missing_or_outside_root") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise BridgeManifestError("package_entry_must_be_regular_file")
    return resolved


def load_manifest(root: str | Path, manifest_name: str = "bridge.json") -> tuple[Path, dict[str, Any]]:
    root_path = Path(root).resolve(strict=True)
    if not root_path.is_dir():
        raise BridgeManifestError("bridge_root_must_be_directory")
    manifest_relative = _safe_relative_path(manifest_name, allow_reserved=True)
    if manifest_relative.as_posix() != "bridge.json":
        raise BridgeManifestError("manifest_must_be_root_bridge_json")
    manifest_path = _resolve_regular_file(root_path, manifest_relative)
    try:
        manifest_bytes = read_regular_file(root_path, manifest_relative, max_bytes=1_048_576)
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BridgeManifestError("manifest_unreadable_or_invalid_json") from exc
    validate_manifest_data(manifest)
    return root_path, manifest


def resolve_package_files(root: Path, manifest: dict[str, Any]) -> list[tuple[str, Path]]:
    resolved: list[tuple[str, Path]] = []
    for raw in manifest["package_files"]:
        relative = _safe_relative_path(raw)
        path = _resolve_regular_file(root, relative)
        resolved.append((relative.as_posix(), path))
    return sorted(resolved, key=lambda item: item[0])

def read_regular_file(root: Path, relative: PurePosixPath, *, max_bytes: int) -> bytes:
    """Read a bounded regular file without following symlink path components."""
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    if hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY"):
        directory_fds: list[int] = []
        file_fd: int | None = None
        try:
            current_fd = os.open(root, flags | os.O_DIRECTORY)
            directory_fds.append(current_fd)
            for part in relative.parts[:-1]:
                current_fd = os.open(
                    part,
                    flags | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=current_fd,
                )
                directory_fds.append(current_fd)
            file_fd = os.open(
                relative.parts[-1],
                flags | os.O_NOFOLLOW,
                dir_fd=directory_fds[-1],
            )
            metadata = os.fstat(file_fd)
            if not stat.S_ISREG(metadata.st_mode):
                raise BridgeManifestError("package_entry_must_be_regular_file")
            if metadata.st_size > max_bytes:
                raise BridgeManifestError("package_file_size_limit_exceeded")
            with os.fdopen(file_fd, "rb") as source:
                file_fd = None
                data = source.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise BridgeManifestError("package_file_size_limit_exceeded")
            return data
        except OSError as exc:
            raise BridgeManifestError("package_file_missing_or_unsafe") from exc
        finally:
            if file_fd is not None:
                os.close(file_fd)
            for descriptor in reversed(directory_fds):
                os.close(descriptor)

    path = _resolve_regular_file(root, relative)
    with path.open("rb") as source:
        metadata = os.fstat(source.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise BridgeManifestError("package_entry_must_be_regular_file")
        if metadata.st_size > max_bytes:
            raise BridgeManifestError("package_file_size_limit_exceeded")
        data = source.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise BridgeManifestError("package_file_size_limit_exceeded")
    return data
