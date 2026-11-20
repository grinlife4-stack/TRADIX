import ast
import json
from pathlib import Path

import pytest

from ecoscan.cli import main
from ecoscan.controls import ControlState, ExecutionGate
from ecoscan.filesystem import FilesystemAdapter
from ecoscan.registry import parse_registry
from ecoscan.runner import ScanRunner
from ecoscan.store import ProjectStore
from ecoscan.transfer import TransferError, export_store, import_store


def source(path, source_id="fs-local", subsystem_id="storage", project_owner="owner-a", operator="operator-a"):
    return {
        "source_id": source_id, "owner_id": project_owner, "operator_id": operator,
        "subsystem_id": subsystem_id, "source_type": "filesystem", "locator": str(path),
        "adapter_id": "filesystem", "adapter_version": "0.1.0", "credential_ref": None,
        "enabled": True, "scope_tags": ["local"],
        "budget": {"max_pages": 100, "max_items": 1000, "timeout_seconds": 20, "max_duration_seconds": 30},
        "expected_measurements": ["logical_bytes", "file_count"],
        "retention_policy": {"history_days": 30, "evidence_days": 0},
        "created_at": "2026-11-20T09:00:00Z", "updated_at": "2026-11-20T09:00:00Z",
    }


def gate(project="project-a", source_id="fs-local"):
    controls = ControlState(True, frozenset({project}), frozenset({(project, "storage")}), frozenset({(project, source_id)}))
    authorizer = lambda actor, pid, owner, operator, sid: (actor, pid, owner, operator, sid) == ("operator-a", project, "owner-a", "operator-a", source_id)
    return ExecutionGate(controls, authorizer)


def test_filesystem_scan_is_metadata_only_and_per_project(tmp_path, monkeypatch):
    root = tmp_path / "source"
    (root / "nested").mkdir(parents=True)
    (root / "a.bin").write_bytes(b"12345")
    (root / "nested" / "b.bin").write_bytes(b"1234567")
    registry = parse_registry({"schema_version": "0.1", "project_id": "project-a", "sources": [source(root)]})
    store = ProjectStore(tmp_path / "db", "project-a")
    monkeypatch.setattr(Path, "open", lambda *a, **k: (_ for _ in ()).throw(AssertionError("source contents must not be opened")))
    outcome = ScanRunner(registry, gate(), {"filesystem": FilesystemAdapter()}, store).run("fs-local", "operator-a")
    assert outcome.coverage_state == "COMPLETE"
    records = store.list_measurements("fs-local")
    assert {x["kind"]: x["value"] for x in records} == {"logical_bytes": 12, "file_count": 2}
    assert (tmp_path / "db" / "project-a.sqlite3").exists()


def test_symlinks_are_skipped_and_mark_scan_partial(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    target = root / "target"
    target.write_bytes(b"data")
    try:
        (root / "link").symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    registry = parse_registry({"schema_version": "0.1", "project_id": "project-a", "sources": [source(root)]})
    store = ProjectStore(tmp_path / "db", "project-a")
    outcome = ScanRunner(registry, gate(), {"filesystem": FilesystemAdapter()}, store).run("fs-local", "operator-a")
    assert outcome.coverage_state == "PARTIAL"
    assert "NON_REGULAR_FILE_SKIPPED" in store.list_coverage()[0]["limitations"]


@pytest.mark.parametrize("fmt", ["json", "jsonl"])
def test_json_and_jsonl_transfer_round_trip_is_idempotent(tmp_path, fmt):
    root = tmp_path / "source"
    root.mkdir()
    (root / "x").write_bytes(b"abc")
    registry = parse_registry({"schema_version": "0.1", "project_id": "project-a", "sources": [source(root)]})
    first = ProjectStore(tmp_path / "db1", "project-a")
    ScanRunner(registry, gate(), {"filesystem": FilesystemAdapter()}, first).run("fs-local", "operator-a")
    paths = export_store(first, tmp_path / "exports", fmt)
    second = ProjectStore(tmp_path / "db2", "project-a")
    assert import_store(paths[0], second) == 3
    assert import_store(paths[0], second) == 0
    assert len(second.list_coverage()) == 1
    assert len(second.list_measurements()) == 2



def test_transfer_rejects_measurement_crossing_source_boundary(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "x").write_bytes(b"abc")
    registry = parse_registry({"schema_version": "0.1", "project_id": "project-a", "sources": [source(root)]})
    store = ProjectStore(tmp_path / "db1", "project-a")
    ScanRunner(registry, gate(), {"filesystem": FilesystemAdapter()}, store).run("fs-local", "operator-a")
    path = export_store(store, tmp_path / "exports", "json")[0]
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["measurements"][0]["source_id"] = "different-source"
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(payload), encoding="utf-8")
    destination = ProjectStore(tmp_path / "db2", "project-a")
    with pytest.raises(TransferError, match="source does not match"):
        import_store(tampered, destination)


def test_transfer_rejects_conflicting_duplicate_measurement_id(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "x").write_bytes(b"abc")
    registry = parse_registry({"schema_version": "0.1", "project_id": "project-a", "sources": [source(root)]})
    original = ProjectStore(tmp_path / "db1", "project-a")
    ScanRunner(registry, gate(), {"filesystem": FilesystemAdapter()}, original).run("fs-local", "operator-a")
    path = export_store(original, tmp_path / "exports", "json")[0]
    destination = ProjectStore(tmp_path / "db2", "project-a")
    assert import_store(path, destination) == 3
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["measurements"][0]["value"] += 1
    tampered = tmp_path / "conflict.json"
    tampered.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(TransferError, match="conflicting duplicate measurement_id"):
        import_store(tampered, destination)


def test_filesystem_adapter_rejects_unsupported_measurement_kind(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    raw = source(root)
    raw["expected_measurements"] = ["allocated_bytes"]
    registry = parse_registry({"schema_version": "0.1", "project_id": "project-a", "sources": [raw]})
    store = ProjectStore(tmp_path / "db", "project-a")
    outcome = ScanRunner(registry, gate(), {"filesystem": FilesystemAdapter()}, store).run("fs-local", "operator-a")
    assert outcome.coverage_state == "FAILED"
    assert outcome.reason_code == "adapter_contract_violation"
    assert store.list_measurements() == []

def test_ecosystem_scope_keeps_each_project_database_separate(tmp_path, capsys):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "one.bin").write_bytes(b"one")
    (second / "two.bin").write_bytes(b"two")
    payload = {
        "schema_version": "0.1",
        "projects": [
            {"project_id": "project-a", "sources": [source(first, "source-a")]},
            {"project_id": "project-b", "sources": [source(second, "source-b", project_owner="owner-b", operator="operator-b")]},
        ],
    }
    registry_path = tmp_path / "ecosystem.json"
    registry_path.write_text(json.dumps(payload), encoding="utf-8")
    controls = {
        "global_enabled": True,
        "enabled_projects": ["project-a", "project-b"],
        "enabled_subsystems": [["project-a", "storage"], ["project-b", "storage"]],
        "enabled_sources": [["project-a", "source-a"], ["project-b", "source-b"]],
        "authorized_actors": [
            ["operator-a", "project-a", "owner-a", "operator-a", "source-a"],
            ["operator-a", "project-b", "owner-b", "operator-b", "source-b"],
        ],
    }
    controls_path = tmp_path / "controls.json"
    controls_path.write_text(json.dumps(controls), encoding="utf-8")
    result = main(["scan", "--registry", str(registry_path), "--controls", str(controls_path), "--actor", "operator-a", "--scope", "ecosystem", "--db-dir", str(tmp_path / "db"), "--export-dir", str(tmp_path / "exports")])
    output = json.loads(capsys.readouterr().out)
    assert result == 0
    assert {x["project_id"] for x in output["outcomes"]} == {"project-a", "project-b"}
    assert (tmp_path / "db" / "project-a.sqlite3").exists()
    assert (tmp_path / "db" / "project-b.sqlite3").exists()


def test_package_has_no_network_or_tradix_runtime_imports():
    root = Path(__file__).resolve().parents[1] / "src" / "ecoscan"
    forbidden = {"urllib", "requests", "httpx", "socket", "subprocess", "boto3", "psycopg"}
    for file in root.rglob("*.py"):
        code = file.read_text(encoding="utf-8")
        assert "from tradix" not in code and "import tradix" not in code
        tree = ast.parse(code)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert imported.isdisjoint(forbidden)
