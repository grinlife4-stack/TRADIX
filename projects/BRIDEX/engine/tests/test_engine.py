import hashlib
import json
import uuid
import zipfile
from pathlib import Path

import pytest

from bridex_engine.manifest import BridgeManifestError, load_manifest, resolve_package_files, validate_manifest_data
from bridex_engine.package import PACKAGE_MANIFEST, build_package, verify_package
from bridex_engine.cli import main
from bridex_engine.scaffold import create_bridge_project


def sample_manifest() -> dict:
    return {
        "manifest_version": "0.1",
        "bridge_id": "urn:uuid:12345678-1234-4234-8234-123456789abc",
        "version": "0.1.0",
        "name": "Example Bridge",
        "owner": {"entity_id": "project:owner", "assignment_ref": "approval:owner-001"},
        "operator": {"entity_id": "operator:primary", "assignment_ref": "approval:operator-001"},
        "obis": {
            "version": "0.1",
            "transport_binding": "loopback-http",
            "security_profile": "development-only",
        },
        "runtime": {"kind": "python", "entrypoint": "src/bridge.py", "independent": True},
        "capabilities": [
            {
                "capability_id": "https://example.invalid/capabilities/catalog.read",
                "version": "1.0.0",
                "scopes": ["catalog:read"],
                "side_effect": "read-only",
                "idempotent": True,
                "timeout_seconds": 15,
                "max_payload_bytes": 65536,
                "input_schema_uri": "https://example.invalid/schemas/catalog-input.json",
                "output_schema_uri": "https://example.invalid/schemas/catalog-output.json",
                "enabled": False,
            }
        ],
        "peers": [],
        "lifecycle": "draft",
        "package_files": ["README.md", "src/bridge.py"],
        "dependencies": [{"name": "python", "version": "3.11+", "license_id": "PSF-2.0"}],
    }


def create_bridge(root: Path) -> Path:
    root.mkdir(parents=True)
    (root / "README.md").write_text("# Example Bridge\n", encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "bridge.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (root / "bridge.json").write_text(json.dumps(sample_manifest(), indent=2), encoding="utf-8")
    return root


def test_canonical_schema_and_packaged_schema_are_byte_identical() -> None:
    engine_schema = Path(__file__).parents[1] / "src" / "bridex_engine" / "schemas" / "bridge-manifest.schema.json"
    canonical_schema = Path(__file__).parents[4] / "standards" / "bridex" / "0.1" / "bridge-manifest.schema.json"
    assert engine_schema.read_bytes() == canonical_schema.read_bytes()


def test_manifest_validation_requires_owner_operator_and_capability_contract() -> None:
    manifest = sample_manifest()
    assert validate_manifest_data(manifest)["bridge_id"] == "urn:uuid:12345678-1234-4234-8234-123456789abc"

    missing_owner = sample_manifest()
    del missing_owner["owner"]
    with pytest.raises(BridgeManifestError, match="manifest_schema_invalid"):
        validate_manifest_data(missing_owner)


def test_manifest_rejects_invalid_uuid_and_duplicate_capabilities() -> None:
    invalid_id = sample_manifest()
    invalid_id["bridge_id"] = "urn:uuid:------------------------------------"
    with pytest.raises(BridgeManifestError, match="bridge_id_must_contain_uuid"):
        validate_manifest_data(invalid_id)

    duplicate = sample_manifest()
    duplicate["capabilities"].append(dict(duplicate["capabilities"][0]))
    with pytest.raises(BridgeManifestError, match="capability_ids_must_be_unique"):
        validate_manifest_data(duplicate)


@pytest.mark.parametrize("bad_path", ["../escape.py", "/etc/passwd", "src/../escape.py", "src\\bridge.py", ".env", "secrets/token.json", "keys/private.pem", "node_modules/pkg/index.js"])
def test_manifest_rejects_unsafe_package_paths(bad_path: str) -> None:
    manifest = sample_manifest()
    manifest["package_files"] = [bad_path]
    with pytest.raises(BridgeManifestError):
        validate_manifest_data(manifest)


def test_source_files_must_exist_and_must_not_be_symlinks(tmp_path: Path) -> None:
    root = create_bridge(tmp_path / "bridge")
    (root / "src" / "bridge.py").unlink()
    outside = tmp_path / "outside.py"
    outside.write_text("outside", encoding="utf-8")
    (root / "src" / "bridge.py").symlink_to(outside)
    _, manifest = load_manifest(root)
    with pytest.raises(BridgeManifestError, match="package_symlink_rejected"):
        resolve_package_files(root, manifest)


def test_build_and_verify_deterministic_independent_package(tmp_path: Path) -> None:
    root = create_bridge(tmp_path / "bridge")
    first = build_package(root, tmp_path / "first.zip")
    second = build_package(root, tmp_path / "second.zip")

    assert first["sha256"] == second["sha256"]
    verified = verify_package(tmp_path / "first.zip")
    assert verified["valid"] is True
    assert verified["bridge_id"] == sample_manifest()["bridge_id"]
    assert verified["file_count"] == 3


def test_package_output_must_be_outside_source_root_and_must_not_overwrite(tmp_path: Path) -> None:
    root = create_bridge(tmp_path / "bridge")
    with pytest.raises(BridgeManifestError, match="package_output_must_be_outside_bridge_root"):
        build_package(root, root / "bridge.zip")
    output = tmp_path / "package.zip"
    build_package(root, output)
    with pytest.raises(BridgeManifestError, match="package_output_already_exists"):
        build_package(root, output)


def test_package_verifier_detects_content_tampering(tmp_path: Path) -> None:
    root = create_bridge(tmp_path / "bridge")
    package = tmp_path / "bridge.zip"
    build_package(root, package)
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(package, "r") as source, zipfile.ZipFile(tampered, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == "src/bridge.py":
                data += b"# altered\n"
            target.writestr(info, data)
    with pytest.raises(BridgeManifestError, match="package_file_integrity_failed"):
        verify_package(tampered)


def test_package_verifier_rejects_unlisted_and_traversal_entries(tmp_path: Path) -> None:
    root = create_bridge(tmp_path / "bridge")
    package = tmp_path / "bridge.zip"
    build_package(root, package)

    for name in ("unexpected.txt", "../escape.txt"):
        altered = tmp_path / (name.replace("/", "_").replace(".", "_") + ".zip")
        with zipfile.ZipFile(package, "r") as source, zipfile.ZipFile(altered, "w", compression=zipfile.ZIP_DEFLATED) as target:
            for info in source.infolist():
                target.writestr(info, source.read(info.filename))
            target.writestr(name, b"unexpected")
        with pytest.raises(BridgeManifestError):
            verify_package(altered)


def test_package_verifier_rejects_duplicate_entries(tmp_path: Path) -> None:
    root = create_bridge(tmp_path / "bridge")
    package = tmp_path / "bridge.zip"
    build_package(root, package)
    duplicate = tmp_path / "duplicate.zip"
    with zipfile.ZipFile(package, "r") as source, zipfile.ZipFile(duplicate, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            target.writestr(info, source.read(info.filename))
        target.writestr("README.md", b"duplicate")
    with pytest.raises(BridgeManifestError, match="package_duplicate_entries_rejected"):
        verify_package(duplicate)


def test_cli_validate_package_and_verify(tmp_path: Path, capsys) -> None:
    root = create_bridge(tmp_path / "bridge")
    assert main(["validate", "--root", str(root)]) == 0
    assert json.loads(capsys.readouterr().out)["valid"] is True
    package = tmp_path / "cli.zip"
    assert main(["package", "--root", str(root), "--output", str(package)]) == 0
    assert json.loads(capsys.readouterr().out)["sha256"]
    assert main(["verify", str(package)]) == 0
    assert json.loads(capsys.readouterr().out)["valid"] is True



def test_manifest_rejects_case_insensitive_package_path_collisions() -> None:
    manifest = sample_manifest()
    manifest["package_files"] = ["Readme.md", "README.md"]
    with pytest.raises(BridgeManifestError, match="package_paths_must_be_unique_case_insensitively"):
        validate_manifest_data(manifest)


def test_verifier_requires_package_file_set_to_match_bridge_manifest(tmp_path: Path) -> None:
    root = create_bridge(tmp_path / "bridge")
    package = tmp_path / "bridge.zip"
    build_package(root, package)
    altered = tmp_path / "manifest-mismatch.zip"
    with zipfile.ZipFile(package, "r") as source:
        original_infos = {info.filename: info for info in source.infolist()}
        entries = {info.filename: source.read(info.filename) for info in source.infolist()}
    manifest = json.loads(entries["bridge.json"].decode("utf-8"))
    manifest["package_files"] = ["README.md"]
    changed_bridge = json.dumps(manifest).encode("utf-8")
    entries["bridge.json"] = changed_bridge
    package_manifest = json.loads(entries[PACKAGE_MANIFEST].decode("utf-8"))
    bridge_record = next(item for item in package_manifest["files"] if item["path"] == "bridge.json")
    bridge_record["size_bytes"] = len(changed_bridge)
    bridge_record["sha256"] = hashlib.sha256(changed_bridge).hexdigest()
    package_manifest["total_bytes"] = sum(item["size_bytes"] for item in package_manifest["files"])
    entries[PACKAGE_MANIFEST] = json.dumps(package_manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    with zipfile.ZipFile(altered, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for name, data in entries.items():
            target.writestr(original_infos[name], data)
    with pytest.raises(BridgeManifestError, match="package_manifest_file_set_mismatch"):
        verify_package(altered)



def test_init_generates_safe_independent_bridge_and_package(tmp_path: Path) -> None:
    root = create_bridge_project(
        tmp_path / "generated",
        name="Sample Independent Bridge",
        owner_id="project:sample-owner",
        owner_assignment_ref="approval:owner-001",
        operator_id="operator:sample",
        operator_assignment_ref="approval:operator-001",
    )
    loaded_root, manifest = load_manifest(root)
    assert loaded_root == root.resolve()
    assert manifest["bridge_id"].startswith("urn:uuid:")
    assert manifest["owner"]["assignment_ref"] == "approval:owner-001"
    assert manifest["operator"]["assignment_ref"] == "approval:operator-001"
    assert manifest["lifecycle"] == "draft"
    assert manifest["peers"] == []
    assert manifest["capabilities"] == []
    assert manifest["obis"]["transport_binding"] == "unconfigured"

    package = tmp_path / "generated-bridge.zip"
    built = build_package(root, package)
    verified = verify_package(package)
    assert built["sha256"] == verified["sha256"]
    assert verified["valid"] is True
    assert verified["bridge_id"] == manifest["bridge_id"]


def test_init_refuses_existing_destination_and_requires_assignment_evidence(tmp_path: Path) -> None:
    destination = tmp_path / "existing"
    destination.mkdir()
    with pytest.raises(FileExistsError, match="bridge_destination_must_not_exist"):
        create_bridge_project(
            destination,
            name="Existing Bridge",
            owner_id="project:owner",
            owner_assignment_ref="approval:owner",
            operator_id="operator:one",
            operator_assignment_ref="approval:operator",
        )
    with pytest.raises(BridgeManifestError):
        create_bridge_project(
            tmp_path / "invalid",
            name="Invalid Bridge",
            owner_id="",
            owner_assignment_ref="",
            operator_id="operator:one",
            operator_assignment_ref="approval:operator",
        )


def test_draft_manifest_cannot_enable_peer_or_capability() -> None:
    enabled_capability = sample_manifest()
    enabled_capability["capabilities"][0]["enabled"] = True
    with pytest.raises(BridgeManifestError, match="draft_bridge_capabilities_must_be_disabled"):
        validate_manifest_data(enabled_capability)

    enabled_peer = sample_manifest()
    enabled_peer["peers"] = [{"peer_id": "remote-peer", "trust_ref": "trust:pending", "enabled": True}]
    with pytest.raises(BridgeManifestError, match="draft_bridge_peers_must_be_disabled"):
        validate_manifest_data(enabled_peer)


def test_draft_manifest_can_start_with_zero_capabilities_and_peers() -> None:
    manifest = sample_manifest()
    manifest["capabilities"] = []
    manifest["peers"] = []
    assert validate_manifest_data(manifest)["capabilities"] == []


def test_cli_init_reports_generated_bridge_identity(tmp_path: Path, capsys) -> None:
    destination = tmp_path / "cli-generated"
    result = main([
        "init",
        "--path", str(destination),
        "--name", "CLI Generated Bridge",
        "--owner-id", "project:owner",
        "--owner-assignment-ref", "approval:owner-001",
        "--operator-id", "operator:one",
        "--operator-assignment-ref", "approval:operator-001",
    ])
    output = json.loads(capsys.readouterr().out)
    assert result == 0
    assert output["created"] is True
    assert output["lifecycle"] == "draft"
    assert output["bridge_id"].startswith("urn:uuid:")
    assert (destination / "bridge.json").is_file()



def test_init_accepts_explicit_uuid_and_preserves_owner_operator_separation(tmp_path: Path) -> None:
    bridge_id = "urn:uuid:aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    root = create_bridge_project(
        tmp_path / "explicit-id",
        name="Explicit Identity Bridge",
        bridge_id=bridge_id,
        owner_id="project:owner",
        owner_assignment_ref="approval:owner",
        operator_id="operator:operator",
        operator_assignment_ref="approval:operator",
    )
    manifest = load_manifest(root)[1]
    assert manifest["bridge_id"] == bridge_id
    assert manifest["owner"]["entity_id"] != manifest["operator"]["entity_id"]
    assert manifest["owner"]["assignment_ref"] != manifest["operator"]["assignment_ref"]



def test_manifest_rejects_duplicate_peer_ids() -> None:
    manifest = sample_manifest()
    peer = {"peer_id": "remote-peer", "trust_ref": "trust:one", "enabled": False}
    manifest["peers"] = [peer, dict(peer)]
    with pytest.raises(BridgeManifestError, match="peer_ids_must_be_unique"):
        validate_manifest_data(manifest)
