"""Generate an owner-specific Bridge project scaffold without inventing runtime behavior."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .layout import verify_package
from .manifest import ManifestValidationError, validate_manifest


_LIFECYCLE = ("build", "deploy", "backup", "restore", "upgrade", "rollback", "revocation", "export", "decommission")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _source_archive(source_root: Path, output: Path) -> None:
    files = sorted(path for path in source_root.rglob("*") if path.is_file())
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            info = zipfile.ZipInfo(path.relative_to(source_root.parent).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def create_bridge_scaffold(
    destination: str | Path,
    *,
    bridge_id: str,
    name: str,
    implementation_version: str,
    owner_id: str,
    owner_name: str,
    operator_id: str,
    operator_name: str,
    obis_versions: list[str] | None = None,
    configuration_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a deterministic, explicitly incomplete Bridge project scaffold."""
    values = (bridge_id, name, implementation_version, owner_id, owner_name, operator_id, operator_name)
    if not all(isinstance(value, str) and value.strip() for value in values):
        raise ManifestValidationError("Bridge identity, owner, and operator fields must be non-empty strings")
    versions = obis_versions or ["0.1"]
    if not versions or not all(isinstance(item, str) and item for item in versions) or len(set(versions)) != len(versions):
        raise ManifestValidationError("OBIS versions must be a non-empty list of unique strings")
    config_schema = configuration_schema or {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "properties": {}}
    try:
        Draft202012Validator.check_schema(config_schema)
    except Exception as exc:
        raise ManifestValidationError("configuration schema is not valid Draft 2020-12 JSON Schema") from exc

    target = Path(destination).resolve()
    if target.exists():
        raise ManifestValidationError("scaffold destination already exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging_parent = Path(tempfile.mkdtemp(prefix=".bridex-scaffold-", dir=target.parent))
    staging = staging_parent / "package"
    try:
        (staging / "artifact").mkdir(parents=True)
        (staging / "records").mkdir()
        (staging / "schemas").mkdir()
        (staging / "src" / "bridge_instance").mkdir(parents=True)
        (staging / "docs" / "lifecycle").mkdir(parents=True)

        ownership_record = {
            "record_version": "0.1",
            "status": "PENDING_OWNER_ATTESTATION",
            "owner": {"id": owner_id, "name": owner_name},
            "operator": {"id": operator_id, "name": operator_name},
            "notice": "Generated placeholder only. Replace with the owner-approved assignment record before release; this file is not proof of ownership."
        }
        _write(staging / "records" / "ownership.json", json.dumps(ownership_record, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        _write(staging / "schemas" / "config.schema.json", json.dumps(config_schema, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        _write(staging / "src" / "bridge_instance" / "README.md", "# Bridge implementation workspace\n\nThis is an intentionally empty implementation scaffold. No network listener, capability handler, credential logic, or production runtime is generated. Implement only against the approved OBIS specification, selected transport/security profile, and the destination peer's explicitly approved contract.\n")
        _write(staging / "README.md", f"# {name}\n\nGenerated BRIDEX scaffold for {bridge_id}.\n\n**Status:** scaffold only; not an executable Bridge and not approved for deployment.\n\nBefore release: implement the approved Bridge behavior, replace the pending ownership record with owner-approved evidence, review credentials and scopes, add tests, and run the conformance and portability gates.\n")
        lifecycle: dict[str, str] = {}
        for action in _LIFECYCLE:
            relative = f"docs/lifecycle/{action}.md"
            lifecycle[action] = relative
            _write(staging / relative, f"# {action.title()} procedure\n\n**Status:** NOT DEFINED.\n\nDocument the owner-approved {action} procedure, preconditions, authorization, failure behavior, recovery, and evidence before release.\n")

        source_archive = staging / "artifact" / "bridge-source.zip"
        _source_archive(staging / "src", source_archive)
        digest = hashlib.sha256(source_archive.read_bytes()).hexdigest()
        manifest = {
            "manifest_version": "0.1",
            "bridge": {"id": bridge_id, "name": name, "implementation_version": implementation_version},
            "ownership": {"owner": {"id": owner_id, "name": owner_name}, "operator": {"id": operator_id, "name": operator_name}, "assignment_record": "records/ownership.json"},
            "source": {"package_uri": "artifact/bridge-source.zip", "sha256": digest},
            "contracts": {"obis_versions": versions, "adapters": []},
            "peers": [],
            "capabilities": [],
            "configuration_schema": "schemas/config.schema.json",
            "dependencies": [],
            "lifecycle": lifecycle,
        }
        validate_manifest(manifest)
        _write(staging / "bridge-manifest.json", json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        report = verify_package(staging)
        os.replace(staging, target)
        return {**report, "destination": str(target), "status": "SCAFFOLD_ONLY_PENDING_IMPLEMENTATION_AND_OWNER_ATTESTATION"}
    except (OSError, ValueError) as exc:
        if isinstance(exc, ManifestValidationError):
            raise
        raise ManifestValidationError("Bridge scaffold generation failed") from exc
    finally:
        shutil.rmtree(staging_parent, ignore_errors=True)
