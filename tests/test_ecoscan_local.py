import ast
import json
from pathlib import Path

import pytest

from tools.ecoscan.local_runtime import (
    EcoscanError, import_export, load_registry, read_measurements,
    run_scan, scan_source, select_sources,
)


def registry(tmp_path, *, enabled=True, source_enabled=True):
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.bin").write_bytes(b"12345")
    (source / "nested").mkdir()
    (source / "nested" / "b.bin").write_bytes(b"1234567")
    payload = {
        "schema_version": 1, "system_enabled": True,
        "projects": [{"project_id": "ALPHA", "enabled": enabled, "sources": [
            {"source_id": "alpha-local", "provider": "filesystem_local", "path": str(source), "enabled": source_enabled}
        ]}]
    }
    config_path = tmp_path / "registry.json"
    config_path.write_text(json.dumps(payload), encoding="utf-8")
    return config_path, source, payload


def test_local_scan_counts_metadata_only(tmp_path):
    cfg, _, _ = registry(tmp_path)
    config, base = load_registry(cfg)
    report = run_scan(config, base, tmp_path / "db", tmp_path / "exports")
    measurement = report["measurements"][0]
    assert (measurement["status"], measurement["file_count"], measurement["bytes"]) == ("COMPLETE", 2, 12)
    assert len(read_measurements(tmp_path / "db", "ALPHA")) == 1


def test_scanner_never_opens_source_file_contents(tmp_path, monkeypatch):
    cfg, _, _ = registry(tmp_path)
    config, base = load_registry(cfg)
    monkeypatch.setattr(Path, "open", lambda *a, **k: (_ for _ in ()).throw(AssertionError("source opened")))
    result = scan_source(config["projects"][0], config["projects"][0]["sources"][0], base)
    assert (result["file_count"], result["bytes"]) == (2, 12)


def test_symlink_files_and_directories_are_not_followed(tmp_path):
    cfg, source, _ = registry(tmp_path)
    try:
        (source / "link.bin").symlink_to(source / "a.bin")
        (source / "linkdir").symlink_to(source / "nested", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    config, base = load_registry(cfg)
    result = run_scan(config, base, tmp_path / "db", tmp_path / "exports")["measurements"][0]
    assert result["file_count"] == 2
    assert "NON_REGULAR_FILE_SKIPPED" in result["warnings"]
    assert "SYMLINK_DIRECTORY_SKIPPED" in result["warnings"]


def test_symlink_root_is_rejected(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(real, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    from tools.ecoscan.local_runtime import _walk_metadata
    with pytest.raises(EcoscanError):
        _walk_metadata(link)


def test_project_source_and_system_switches(tmp_path):
    cfg, _, payload = registry(tmp_path, enabled=False)
    config, base = load_registry(cfg)
    report = run_scan(config, base, tmp_path / "db", tmp_path / "out")
    assert report["measurements"][0]["status"] == "DISABLED"
    assert report["measurements"][0]["bytes"] is None
    payload["projects"][0]["enabled"] = True
    payload["projects"][0]["sources"][0]["enabled"] = False
    payload["system_enabled"] = False
    cfg.write_text(json.dumps(payload), encoding="utf-8")
    config, base = load_registry(cfg)
    report = run_scan(config, base, tmp_path / "db2", tmp_path / "out2")
    assert report == {"status": "DISABLED", "measurements": [], "exports": []}
    assert not (tmp_path / "db2").exists()


def test_remote_provider_is_rejected_in_phase_one(tmp_path):
    cfg, _, payload = registry(tmp_path)
    payload["projects"][0]["sources"][0]["provider"] = "github"
    cfg.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(EcoscanError, match="filesystem_local only"):
        load_registry(cfg)


def test_duplicate_ids_are_rejected(tmp_path):
    cfg, _, payload = registry(tmp_path)
    payload["projects"].append(payload["projects"][0])
    cfg.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(EcoscanError, match="duplicate project_id"):
        load_registry(cfg)


def test_scope_selection_is_strict(tmp_path):
    cfg, _, _ = registry(tmp_path)
    config, _ = load_registry(cfg)
    assert len(select_sources(config, "project", project_id="ALPHA")) == 1
    assert len(select_sources(config, "source", source_id="alpha-local")) == 1
    with pytest.raises(EcoscanError):
        select_sources(config, "project")
    with pytest.raises(EcoscanError):
        select_sources(config, "source", source_id="missing")


def test_each_project_has_an_independent_sqlite_database(tmp_path):
    cfg, source, payload = registry(tmp_path)
    payload["projects"].append({"project_id": "BETA", "sources": [
        {"source_id": "beta-local", "provider": "filesystem_local", "path": str(source)}
    ]})
    cfg.write_text(json.dumps(payload), encoding="utf-8")
    config, base = load_registry(cfg)
    run_scan(config, base, tmp_path / "db", tmp_path / "exports")
    assert (tmp_path / "db" / "ALPHA.sqlite3").exists()
    assert (tmp_path / "db" / "BETA.sqlite3").exists()
    assert len(read_measurements(tmp_path / "db", "ALPHA")) == 1
    assert len(read_measurements(tmp_path / "db", "BETA")) == 1


@pytest.mark.parametrize("fmt", ["json", "jsonl", "both"])
def test_json_and_jsonl_exports(tmp_path, fmt):
    cfg, _, _ = registry(tmp_path)
    config, base = load_registry(cfg)
    run_scan(config, base, tmp_path / "db", tmp_path / "exports", fmt=fmt)
    if fmt in ("json", "both"):
        assert (tmp_path / "exports" / "ALPHA.json").exists()
    if fmt in ("jsonl", "both"):
        assert (tmp_path / "exports" / "ALPHA.jsonl").exists()


@pytest.mark.parametrize("suffix", ["json", "jsonl"])
def test_export_import_round_trip_is_idempotent(tmp_path, suffix):
    cfg, _, _ = registry(tmp_path)
    config, base = load_registry(cfg)
    run_scan(config, base, tmp_path / "db1", tmp_path / "exports")
    source = tmp_path / "exports" / f"ALPHA.{suffix}"
    assert import_export(source, tmp_path / "db2", "ALPHA") == 1
    assert import_export(source, tmp_path / "db2", "ALPHA") == 0
    assert read_measurements(tmp_path / "db1", "ALPHA") == read_measurements(tmp_path / "db2", "ALPHA")


def test_import_rejects_negative_sizes(tmp_path):
    cfg, _, _ = registry(tmp_path)
    config, base = load_registry(cfg)
    run_scan(config, base, tmp_path / "db1", tmp_path / "exports", fmt="json")
    payload = json.loads((tmp_path / "exports" / "ALPHA.json").read_text())
    payload["measurements"][0]["bytes"] = -1
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(payload))
    with pytest.raises(EcoscanError, match="invalid bytes"):
        import_export(bad, tmp_path / "db2", "ALPHA")


def test_missing_source_is_partial_not_zero(tmp_path):
    cfg, _, payload = registry(tmp_path)
    payload["projects"][0]["sources"][0]["path"] = str(tmp_path / "missing")
    cfg.write_text(json.dumps(payload), encoding="utf-8")
    config, base = load_registry(cfg)
    measurement = run_scan(config, base, tmp_path / "db", tmp_path / "exports")["measurements"][0]
    assert measurement["status"] == "PARTIAL"
    assert measurement["bytes"] is None


def test_default_entrypoint_uses_local_runtime_only():
    root = Path(__file__).resolve().parent.parent
    content = (root / "tools/ecoscan/__main__.py").read_text(encoding="utf-8")
    assert "local_runtime" in content
    assert "monitor" not in content


def test_local_runtime_has_no_network_or_external_process_imports():
    root = Path(__file__).resolve().parent.parent
    source = (root / "tools/ecoscan/local_runtime.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    forbidden = {"urllib", "requests", "httpx", "socket", "subprocess", "boto3", "psycopg"}
    assert imported.isdisjoint(forbidden)
