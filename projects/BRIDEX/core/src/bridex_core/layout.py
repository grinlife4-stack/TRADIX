"""Portable Bridge package layout verification with path traversal protection."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
from typing import Any

from .manifest import ManifestValidationError, load_manifest


MANIFEST_NAME = "bridge-manifest.json"


def _package_file(root: Path, reference: str, field: str) -> Path:
    if not isinstance(reference, str) or not reference or "\\" in reference:
        raise ManifestValidationError(f"{field}: expected a non-empty POSIX relative path")
    relative = PurePosixPath(reference)
    if relative.is_absolute() or any(part in ("", ".", "..") for part in relative.parts):
        raise ManifestValidationError(f"{field}: absolute paths and traversal segments are forbidden")
    candidate = root.joinpath(*relative.parts)
    try:
        resolved_root = root.resolve(strict=True)
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(resolved_root)
    except (OSError, ValueError) as exc:
        raise ManifestValidationError(f"{field}: referenced file is missing or escapes package root") from exc
    if not resolved.is_file():
        raise ManifestValidationError(f"{field}: referenced path is not a regular file")
    return resolved


def verify_package(root: str | Path) -> dict[str, Any]:
    """Validate manifest references and artifact digest inside an exported package."""
    package_root = Path(root)
    if not package_root.is_dir():
        raise ManifestValidationError("package root is not a directory")
    manifest = load_manifest(package_root / MANIFEST_NAME)

    artifact = _package_file(package_root, manifest["source"]["package_uri"], "source.package_uri")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    if digest.lower() != manifest["source"]["sha256"].lower():
        raise ManifestValidationError("source.sha256: artifact digest mismatch")

    ownership_record = _package_file(package_root, manifest["ownership"]["assignment_record"], "ownership.assignment_record")
    configuration = _package_file(package_root, manifest["configuration_schema"], "configuration_schema")
    for name, reference in manifest["lifecycle"].items():
        _package_file(package_root, reference, f"lifecycle.{name}")

    return {
        "bridge_id": manifest["bridge"]["id"],
        "artifact": artifact.relative_to(package_root.resolve()).as_posix(),
        "sha256": digest,
        "configuration_schema": configuration.relative_to(package_root.resolve()).as_posix(),
        "ownership_assignment_record": ownership_record.relative_to(package_root.resolve()).as_posix(),
        "lifecycle_documents": len(manifest["lifecycle"]),
    }
