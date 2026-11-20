from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from bridex_core.generator import create_bridge_project
from bridex_core.manifest import ManifestError, load_manifest, validate_manifest
from bridex_core.package import PackageError, package_bridge


def manifest() -> dict:
    return {
        "format_version": "1",
        "bridge_id": "nexora-catalog",
        "name": "Nexora Catalog Bridge",
        "version": "0.1.0",
        "owner": {"id": "nexora", "assignment_ref": "decision:owner-001"},
        "operator": {"id": "ops-team", "assignment_ref": "decision:operator-001"},
        "maintainer": None,
        "protocols": {"obis": "0.1"},
        "peers": [],
        "capabilities": [],
        "lifecycle": "draft",
    }


def create(tmp_path: Path) -> Path:
    return create_bridge_project(
        tmp_path / "bridge",
        bridge_id="nexora-catalog",
        name="Nexora Catalog Bridge",
        owner_id="nexora",
        owner_assignment_ref="decision:owner-001",
        operator_id="ops-team",
        operator_assignment_ref="decision:operator-001",
    )


def test_manifest_requires_explicit_owner_and_operator_assignment() -> None:
    value = manifest()
    del value["owner"]["assignment_ref"]
    with pytest.raises(ManifestError, match="owner_assignment_evidence_required"):
        validate_manifest(value)


def test_manifest_rejects_unknown_fields_and_non_semver() -> None:
    value = manifest()
    value["unexpected"] = "must not silently pass"
    with pytest.raises(ManifestError, match="unknown_manifest_fields"):
        validate_manifest(value)
    value = manifest()
    value["version"] = "latest"
    with pytest.raises(ManifestError, match="invalid_semver"):
        validate_manifest(value)


def test_peers_and_capabilities_must_start_disabled() -> None:
    value = manifest()
    value["peers"] = [{"peer_id": "remote-peer", "trust_ref": "trust:pending", "enabled": True}]
    with pytest.raises(ManifestError, match="new_peers_must_start_disabled"):
        validate_manifest(value)
    value = manifest()
    value["capabilities"] = [{
        "capability_id": "catalog.read",
        "version": "1.0.0",
        "required_scopes": ["catalog:read"],
        "enabled": True,
    }]
    with pytest.raises(ManifestError, match="new_capabilities_must_start_disabled"):
        validate_manifest(value)


def test_generator_creates_independent_draft_project(tmp_path: Path) -> None:
    root = create(tmp_path)
    data = load_manifest(root)
    assert data["owner"]["id"] == "nexora"
    assert data["operator"]["id"] == "ops-team"
    assert data["lifecycle"] == "draft"
    assert data["peers"] == []
    assert data["capabilities"] == []
    assert not (root / ".env").exists()
    assert (root / "src" / "nexora_catalog_bridge" / "__init__.py").is_file()
    assert (root / "src" / "obis_bridge" / "peer.py").is_file()
    assert (root / "src" / "obis_bridge" / "schemas" / "message.schema.json").is_file()
    assert (root / "pyproject.toml").is_file()


def test_generator_refuses_to_overwrite_existing_destination(tmp_path: Path) -> None:
    root = create(tmp_path)
    with pytest.raises(FileExistsError, match="destination_must_not_exist"):
        create_bridge_project(
            root,
            bridge_id="nexora-catalog",
            name="Nexora Catalog Bridge",
            owner_id="nexora",
            owner_assignment_ref="decision:owner-001",
            operator_id="ops-team",
            operator_assignment_ref="decision:operator-001",
        )


def test_package_is_reproducible_and_contains_only_project_sources(tmp_path: Path) -> None:
    root = create(tmp_path)
    out_a = tmp_path / "a.zip"
    out_b = tmp_path / "b.zip"
    _, digest_a = package_bridge(root, out_a)
    _, digest_b = package_bridge(root, out_b)
    assert digest_a == digest_b
    with zipfile.ZipFile(out_a) as archive:
        names = set(archive.namelist())
    assert "bridex.json" in names
    assert "README.md" in names
    assert "pyproject.toml" in names
    assert "config/bridge.example.json" in names
    assert "src/nexora_catalog_bridge/__init__.py" in names
    assert not any(".env" in name or "__pycache__" in name for name in names)


def test_package_rejects_secret_named_files(tmp_path: Path) -> None:
    root = create(tmp_path)
    (root / "src" / "nexora_catalog_bridge" / "credentials.json").write_text(
        '{"token":"not-a-real-token"}', encoding="utf-8"
    )
    with pytest.raises(PackageError, match="secret_file_not_allowed"):
        package_bridge(root, tmp_path / "bridge.zip")


def test_package_rejects_symlinked_source(tmp_path: Path) -> None:
    root = create(tmp_path)
    outside = tmp_path / "outside.py"
    outside.write_text("private = True", encoding="utf-8")
    link = root / "src" / "nexora_catalog_bridge" / "external.py"
    link.symlink_to(outside)
    with pytest.raises(PackageError, match="symlink_not_allowed"):
        package_bridge(root, tmp_path / "bridge.zip")


def test_package_rejects_private_key_material_even_when_filename_looks_safe(tmp_path: Path) -> None:
    root = create(tmp_path)
    private_file = root / "src" / "nexora_catalog_bridge" / "settings.py"
    private_file.write_text(
        'PRIVATE_KEY = "-----BEGIN PRIVATE KEY-----"',
        encoding="utf-8",
    )
    with pytest.raises(PackageError, match="secret_material_detected"):
        package_bridge(root, tmp_path / "bridge.zip")


def test_package_rejects_symlink_output_path(tmp_path: Path) -> None:
    root = create(tmp_path)
    actual = tmp_path / "actual.zip"
    actual.write_bytes(b"do-not-overwrite")
    link = tmp_path / "linked.zip"
    link.symlink_to(actual)
    with pytest.raises(PackageError, match="package_output_symlink_not_allowed"):
        package_bridge(root, link)
    assert actual.read_bytes() == b"do-not-overwrite"


def test_vendored_obis_template_matches_standalone_reference() -> None:
    repository = Path(__file__).parents[4]
    core = Path(__file__).parents[1]
    reference = repository / "projects" / "BRIDEX" / "reference" / "obis-python" / "src" / "obis_bridge"
    template = core / "src" / "bridex_core" / "templates" / "obis_bridge"
    assert (template / "peer.py").read_bytes() == (reference / "peer.py").read_bytes()
    assert (template / "schemas" / "message.schema.json").read_bytes() == (
        reference / "schemas" / "message.schema.json"
    ).read_bytes()


def test_generated_bridge_obis_peer_runs_without_tradix_or_bridex_runtime(tmp_path: Path) -> None:
    import os
    import subprocess
    import sys

    root = create(tmp_path)
    script = r'''
from obis_bridge import Credential, OBISClient, OBISPeer, OBISServer

secret = b"0123456789abcdef0123456789abcdef"
credential = Credential(
    key_id="generated-test-key",
    peer_id="independent-caller",
    principal_ref="principal:test",
    secret=secret,
    allowed_scopes=frozenset({"demo:read"}),
)
peer = OBISPeer("generated-bridge", [credential])
peer.register_capability(
    "demo.echo", "1.0", {"demo:read"},
    lambda payload: {"echo": payload["value"]},
)
client = OBISClient(
    local_peer_id="independent-caller",
    remote_peer_id="generated-bridge",
    key_id="generated-test-key",
    principal_ref="principal:test",
    secret=secret,
    scopes={"demo:read"},
)
with OBISServer(peer) as server:
    response = client.invoke(server.address, "demo.echo", "1.0", {"value": "independent"})
assert response["result"]["echo"] == "independent"
'''
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(root / "src")
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
