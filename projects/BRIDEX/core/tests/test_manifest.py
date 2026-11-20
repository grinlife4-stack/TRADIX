import json

import pytest

from bridex_core import ManifestValidationError, load_manifest, load_schema, validate_manifest


VALID = {
    "manifest_version": "0.1",
    "bridge": {"id": "urn:uuid:00000000-0000-4000-8000-000000000001", "name": "Example Bridge", "implementation_version": "0.1.0"},
    "ownership": {
        "owner": {"id": "project:alpha", "name": "Alpha"},
        "operator": {"id": "operator:alpha", "name": "Alpha Operations"},
        "assignment_record": "records/ownership.json"
    },
    "source": {"package_uri": "file:./bridge.tar.gz", "sha256": "a" * 64},
    "contracts": {"obis_versions": ["0.1"], "adapters": []},
    "peers": [{"peer_id": "peer:beta", "approved_scopes": ["records:read"]}],
    "capabilities": [{"id": "records.read", "version": "1.0", "direction": "consumes", "scopes": ["records:read"]}],
    "configuration_schema": "schemas/config.schema.json",
    "dependencies": [{"name": "stdlib", "version": "3.12", "license": "PSF-2.0"}],
    "lifecycle": {
        "build": "docs/build.md", "deploy": "docs/deploy.md", "backup": "docs/backup.md",
        "restore": "docs/restore.md", "upgrade": "docs/upgrade.md", "rollback": "docs/rollback.md",
        "revocation": "docs/revocation.md", "export": "docs/export.md", "decommission": "docs/decommission.md"
    }
}


def test_schema_is_valid_draft_2020_12():
    assert load_schema()["$schema"].endswith("2020-12/schema")


def test_valid_manifest_is_returned_unchanged():
    assert validate_manifest(VALID) is VALID


def test_missing_owner_is_rejected():
    candidate = json.loads(json.dumps(VALID))
    del candidate["ownership"]["owner"]
    with pytest.raises(ManifestValidationError, match="owner"):
        validate_manifest(candidate)


def test_unknown_top_level_field_is_rejected():
    candidate = {**VALID, "runtime_secret": "must-not-be-here"}
    with pytest.raises(ManifestValidationError, match="Additional properties"):
        validate_manifest(candidate)


def test_duplicate_json_keys_are_rejected(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text('{"manifest_version":"0.1","manifest_version":"0.1"}', encoding="utf-8")
    with pytest.raises(ManifestValidationError, match="duplicate JSON object key"):
        load_manifest(path)


def test_valid_manifest_can_be_loaded_from_file(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(VALID), encoding="utf-8")
    assert load_manifest(path)["bridge"]["name"] == "Example Bridge"


def test_cli_accepts_valid_manifest(tmp_path, capsys):
    from bridex_core.cli import main
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(VALID), encoding="utf-8")
    assert main(["validate", str(path)]) == 0
    assert "valid:" in capsys.readouterr().out


def test_cli_rejects_invalid_manifest(tmp_path, capsys):
    from bridex_core.cli import main
    path = tmp_path / "manifest.json"
    path.write_text('{"manifest_version":"invalid"}', encoding="utf-8")
    assert main(["validate", str(path)]) == 2
    assert "invalid:" in capsys.readouterr().err
