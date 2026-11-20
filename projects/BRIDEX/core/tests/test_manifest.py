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
    "source": {"package_uri": "artifact/bridge.tar.gz", "sha256": "a" * 64},
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


def _write_portable_package(root):
    import hashlib
    root.mkdir(parents=True, exist_ok=True)
    artifact = root / "artifact" / "bridge.tar"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"independent bridge artifact")
    (root / "records").mkdir()
    (root / "records" / "ownership.json").write_text('{"owner":"project:alpha"}', encoding="utf-8")
    (root / "schemas").mkdir()
    (root / "schemas" / "config.schema.json").write_text('{"type":"object"}', encoding="utf-8")
    (root / "docs" / "lifecycle").mkdir(parents=True)
    lifecycle = {}
    for name in ("build", "deploy", "backup", "restore", "upgrade", "rollback", "revocation", "export", "decommission"):
        relative = f"docs/lifecycle/{name}.md"
        (root / relative).write_text(f"# {name}", encoding="utf-8")
        lifecycle[name] = relative
    data = json.loads(json.dumps(VALID))
    data["source"]["package_uri"] = "artifact/bridge.tar"
    data["source"]["sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
    data["configuration_schema"] = "schemas/config.schema.json"
    data["lifecycle"] = lifecycle
    (root / "bridge-manifest.json").write_text(json.dumps(data), encoding="utf-8")
    return root


def test_portable_package_verifies_artifact_and_all_referenced_files(tmp_path):
    from bridex_core import verify_package
    package = _write_portable_package(tmp_path / "export")
    report = verify_package(package)
    assert report["bridge_id"] == VALID["bridge"]["id"]
    assert report["lifecycle_documents"] == 9


def test_portable_package_rejects_artifact_digest_mismatch(tmp_path):
    from bridex_core import verify_package
    package = _write_portable_package(tmp_path / "export")
    (package / "artifact" / "bridge.tar").write_bytes(b"tampered")
    with pytest.raises(ManifestValidationError, match="digest mismatch"):
        verify_package(package)


def test_portable_package_rejects_path_traversal(tmp_path):
    from bridex_core import verify_package
    package = _write_portable_package(tmp_path / "export")
    manifest = json.loads((package / "bridge-manifest.json").read_text())
    manifest["source"]["package_uri"] = "../outside.tar"
    (package / "bridge-manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ManifestValidationError, match="traversal"):
        verify_package(package)


def test_portable_package_rejects_symlink_escape(tmp_path):
    from bridex_core import verify_package
    package = _write_portable_package(tmp_path / "export")
    outside = tmp_path / "outside.tar"
    outside.write_bytes(b"external")
    (package / "artifact" / "bridge.tar").unlink()
    (package / "artifact" / "bridge.tar").symlink_to(outside)
    with pytest.raises(ManifestValidationError, match="escapes package root"):
        verify_package(package)


def test_cli_verifies_portable_package(tmp_path, capsys):
    from bridex_core.cli import main
    package = _write_portable_package(tmp_path / "export")
    assert main(["verify-package", str(package)]) == 0
    assert "valid: BRIDEX portable Bridge package" in capsys.readouterr().out


def test_package_export_is_deterministic_and_restore_is_verified(tmp_path):
    import hashlib
    from bridex_core import export_package, restore_package
    package = _write_portable_package(tmp_path / "package")
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    export_package(package, first)
    export_package(package, second)
    assert hashlib.sha256(first.read_bytes()).digest() == hashlib.sha256(second.read_bytes()).digest()
    restored = restore_package(first, tmp_path / "restored")
    assert restored["bridge_id"] == VALID["bridge"]["id"]
    assert (tmp_path / "restored" / "bridge-manifest.json").is_file()


def test_restore_rejects_zip_path_traversal(tmp_path):
    import zipfile
    from bridex_core import restore_package
    archive = tmp_path / "malicious.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("../escaped.txt", "must not be written")
    with pytest.raises(ManifestValidationError, match="traversal"):
        restore_package(archive, tmp_path / "restored")
    assert not (tmp_path / "escaped.txt").exists()
    assert not (tmp_path / "restored").exists()


def test_export_rejects_output_inside_package_root(tmp_path):
    from bridex_core import export_package
    package = _write_portable_package(tmp_path / "package")
    with pytest.raises(ManifestValidationError, match="outside"):
        export_package(package, package / "nested.zip")


def test_restore_refuses_to_overwrite_existing_directory(tmp_path):
    from bridex_core import export_package, restore_package
    package = _write_portable_package(tmp_path / "package")
    archive = tmp_path / "package.zip"
    export_package(package, archive)
    destination = tmp_path / "existing"
    destination.mkdir()
    with pytest.raises(ManifestValidationError, match="already exists"):
        restore_package(archive, destination)


def test_export_rejects_symlinked_directory(tmp_path):
    from bridex_core import export_package
    package = _write_portable_package(tmp_path / "package")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("not part of package", encoding="utf-8")
    (package / "external").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ManifestValidationError, match="symlinks"):
        export_package(package, tmp_path / "package.zip")


def test_restore_rejects_symlink_entries(tmp_path):
    import stat
    import zipfile
    from bridex_core import restore_package
    archive = tmp_path / "symlink.zip"
    info = zipfile.ZipInfo("bridge-manifest.json")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(info, "outside-target")
    with pytest.raises(ManifestValidationError, match="symlink or special file"):
        restore_package(archive, tmp_path / "restored")
    assert not (tmp_path / "restored").exists()


def test_published_obis_schema_conformance_vectors_pass():
    from pathlib import Path
    from bridex_core import run_schema_suite
    repo_root = Path(__file__).resolve().parents[4]
    suite = repo_root / "standards" / "obis" / "0.1" / "conformance" / "vectors.json"
    report = run_schema_suite(suite)
    assert report["result"] == "passed"
    assert report["vectors"] == 7
    assert report["accepted"] == 3
    assert report["rejected"] == 4


def test_obis_schema_conformance_runner_fails_on_wrong_expected_result(tmp_path):
    import shutil
    from pathlib import Path
    from bridex_core import ConformanceSuiteError, run_schema_suite
    repo_root = Path(__file__).resolve().parents[4]
    source = repo_root / "standards" / "obis" / "0.1"
    target = tmp_path / "standards" / "obis" / "0.1"
    (target / "conformance").mkdir(parents=True)
    shutil.copyfile(source / "message.schema.json", target / "message.schema.json")
    shutil.copyfile(source / "conformance" / "suite.schema.json", target / "conformance" / "suite.schema.json")
    suite_data = json.loads((source / "conformance" / "vectors.json").read_text(encoding="utf-8"))
    suite_data["vectors"][0]["expected"] = "reject"
    (target / "conformance" / "vectors.json").write_text(json.dumps(suite_data), encoding="utf-8")
    with pytest.raises(ConformanceSuiteError, match="request.valid.basic"):
        run_schema_suite(target / "conformance" / "vectors.json")


def test_cli_runs_published_obis_schema_conformance_suite(tmp_path, capsys):
    from pathlib import Path
    from bridex_core.cli import main
    repo_root = Path(__file__).resolve().parents[4]
    suite = repo_root / "standards" / "obis" / "0.1" / "conformance" / "vectors.json"
    assert main(["conformance", "schema", str(suite)]) == 0
    assert "passed: OBIS schema conformance suite" in capsys.readouterr().out
