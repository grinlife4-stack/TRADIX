import ast
import json
from pathlib import Path

import pytest

from ecoscan.cli import main
from ecoscan.contracts import BudgetExceeded, BudgetGuard
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
    outcome = ScanRunner(registry, gate(), {"filesystem": FilesystemAdapter(tmp_path, allowed_root=tmp_path)}, store).run("fs-local", "operator-a")
    assert outcome.coverage_state == "COMPLETE"
    records = store.list_measurements("fs-local")
    assert {x["kind"]: x["value"] for x in records} == {"logical_bytes": 12, "file_count": 2}
    assert (tmp_path / "db" / "project-a.sqlite3").exists()


@pytest.mark.parametrize("file_count,total_bytes", [(0, 0), (1, 5)])
def test_aggregate_measurements_work_for_empty_and_single_file_sources(tmp_path, file_count, total_bytes):
    root = tmp_path / "source"
    root.mkdir()
    for index in range(file_count):
        (root / f"file-{index}.bin").write_bytes(b"x" * 5)
    parsed = parse_registry({
        "schema_version": "0.1",
        "project_id": "project-a",
        "sources": [source(root)],
    })
    store = ProjectStore(tmp_path / "db", "project-a")
    outcome = ScanRunner(parsed, gate(), {"filesystem": FilesystemAdapter(tmp_path, allowed_root=tmp_path)}, store).run(
        "fs-local", "operator-a"
    )
    assert outcome.coverage_state == "COMPLETE"
    records = store.list_measurements("fs-local")
    assert {item["kind"]: item["value"] for item in records} == {
        "logical_bytes": total_bytes,
        "file_count": file_count,
    }


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
    outcome = ScanRunner(registry, gate(), {"filesystem": FilesystemAdapter(tmp_path, allowed_root=tmp_path)}, store).run("fs-local", "operator-a")
    assert outcome.coverage_state == "PARTIAL"
    assert "NON_REGULAR_FILE_SKIPPED" in store.list_coverage()[0]["limitations"]


@pytest.mark.parametrize("fmt", ["json", "jsonl"])
def test_json_and_jsonl_transfer_round_trip_is_idempotent(tmp_path, fmt):
    root = tmp_path / "source"
    root.mkdir()
    (root / "x").write_bytes(b"abc")
    registry = parse_registry({"schema_version": "0.1", "project_id": "project-a", "sources": [source(root)]})
    first = ProjectStore(tmp_path / "db1", "project-a")
    ScanRunner(registry, gate(), {"filesystem": FilesystemAdapter(tmp_path, allowed_root=tmp_path)}, first).run("fs-local", "operator-a")
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
    ScanRunner(registry, gate(), {"filesystem": FilesystemAdapter(tmp_path, allowed_root=tmp_path)}, store).run("fs-local", "operator-a")
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
    ScanRunner(registry, gate(), {"filesystem": FilesystemAdapter(tmp_path, allowed_root=tmp_path)}, original).run("fs-local", "operator-a")
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
    outcome = ScanRunner(registry, gate(), {"filesystem": FilesystemAdapter(tmp_path, allowed_root=tmp_path)}, store).run("fs-local", "operator-a")
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


def test_filesystem_adapter_rejects_absolute_path_outside_allowed_root(tmp_path):
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    (outside / "secret.bin").write_bytes(b"not in scope")
    registry = parse_registry({
        "schema_version": "0.1",
        "project_id": "project-a",
        "sources": [source(outside)],
    })
    store = ProjectStore(tmp_path / "db", "project-a")
    outcome = ScanRunner(
        registry,
        gate(),
        {"filesystem": FilesystemAdapter(allowed, allowed_root=allowed)},
        store,
    ).run("fs-local", "operator-a")
    assert outcome.coverage_state == "FAILED"
    assert outcome.reason_code == "adapter_contract_violation"
    assert store.list_measurements() == []


def test_filesystem_adapter_rejects_parent_traversal_outside_allowed_root(tmp_path):
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    (outside / "secret.bin").write_bytes(b"not in scope")
    registry = parse_registry({
        "schema_version": "0.1",
        "project_id": "project-a",
        "sources": [source("../outside")],
    })
    store = ProjectStore(tmp_path / "db", "project-a")
    outcome = ScanRunner(
        registry,
        gate(),
        {"filesystem": FilesystemAdapter(allowed, allowed_root=allowed)},
        store,
    ).run("fs-local", "operator-a")
    assert outcome.coverage_state == "FAILED"
    assert outcome.reason_code == "adapter_contract_violation"
    assert store.list_measurements() == []


def test_filesystem_adapter_rejects_symlink_in_parent_path(tmp_path):
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    (outside / "secret.bin").write_bytes(b"not in scope")
    link = allowed / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("directory symlinks unavailable")
    registry = parse_registry({
        "schema_version": "0.1",
        "project_id": "project-a",
        "sources": [source(link)],
    })
    store = ProjectStore(tmp_path / "db", "project-a")
    outcome = ScanRunner(
        registry,
        gate(),
        {"filesystem": FilesystemAdapter(allowed, allowed_root=allowed)},
        store,
    ).run("fs-local", "operator-a")
    assert outcome.coverage_state == "FAILED"
    assert outcome.reason_code == "adapter_contract_violation"
    assert store.list_measurements() == []



@pytest.mark.parametrize(
    "controls",
    [
        ControlState(False, frozenset({"project-a"}), frozenset({("project-a", "storage")}), frozenset({("project-a", "fs-local")})),
        ControlState(True, frozenset(), frozenset({("project-a", "storage")}), frozenset({("project-a", "fs-local")})),
        ControlState(True, frozenset({"project-a"}), frozenset(), frozenset({("project-a", "fs-local")})),
        ControlState(True, frozenset({"project-a"}), frozenset({("project-a", "storage")}), frozenset()),
    ],
    ids=["global-off", "project-off", "subsystem-off", "source-off"],
)
def test_each_disabled_control_blocks_adapter_execution(tmp_path, controls):
    root = tmp_path / "source"
    root.mkdir()
    registry = parse_registry({
        "schema_version": "0.1",
        "project_id": "project-a",
        "sources": [source(root)],
    })

    class CountingAdapter:
        adapter_id = "filesystem"
        version = "0.1.0"

        def __init__(self):
            self.calls = 0

        def validate_config(self, descriptor):
            self.calls += 1

        def scan(self, context):
            self.calls += 1
            raise AssertionError("disabled source must never reach adapter execution")

    adapter = CountingAdapter()
    disabled_gate = ExecutionGate(controls, lambda *args: True)
    store = ProjectStore(tmp_path / "db", "project-a")
    outcome = ScanRunner(registry, disabled_gate, {"filesystem": adapter}, store).run(
        "fs-local", "operator-a"
    )
    assert outcome.coverage_state == "DISABLED"
    assert adapter.calls == 0
    assert store.list_measurements() == []


@pytest.mark.parametrize("budget_key,budget_value", [("max_items", 1), ("max_pages", 1)])
def test_filesystem_budget_exhaustion_fails_without_measurements(tmp_path, budget_key, budget_value):
    root = tmp_path / "source"
    (root / "nested").mkdir(parents=True)
    (root / "one.bin").write_bytes(b"1")
    (root / "two.bin").write_bytes(b"22")
    (root / "nested" / "three.bin").write_bytes(b"333")
    raw = source(root)
    raw["budget"][budget_key] = budget_value
    registry = parse_registry({
        "schema_version": "0.1",
        "project_id": "project-a",
        "sources": [raw],
    })
    store = ProjectStore(tmp_path / "db", "project-a")
    outcome = ScanRunner(
        registry,
        gate(),
        {"filesystem": FilesystemAdapter(tmp_path, allowed_root=tmp_path)},
        store,
    ).run("fs-local", "operator-a")
    assert outcome.coverage_state == "FAILED"
    assert outcome.reason_code == "budget_exhausted"
    assert store.list_measurements() == []


@pytest.mark.parametrize("suffix,raw", [(".json", "{broken"), (".jsonl", '{"type":"manifest"}\n{broken\n')])
def test_transfer_rejects_corrupted_json_and_jsonl_without_partial_import(tmp_path, suffix, raw):
    destination = ProjectStore(tmp_path / "destination", "project-a")
    corrupted = tmp_path / f"corrupted{suffix}"
    corrupted.write_text(raw, encoding="utf-8")
    with pytest.raises(TransferError):
        import_store(corrupted, destination)
    assert destination.list_coverage() == []
    assert destination.list_measurements() == []


def test_transfer_rejects_manifest_count_tampering_without_partial_import(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "x").write_bytes(b"abc")
    registry = parse_registry({
        "schema_version": "0.1",
        "project_id": "project-a",
        "sources": [source(root)],
    })
    original = ProjectStore(tmp_path / "original", "project-a")
    ScanRunner(
        registry,
        gate(),
        {"filesystem": FilesystemAdapter(tmp_path, allowed_root=tmp_path)},
        original,
    ).run("fs-local", "operator-a")
    path = export_store(original, tmp_path / "exports", "json")[0]
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["manifest"]["measurement_count"] += 1
    tampered = tmp_path / "count-tampered.json"
    tampered.write_text(json.dumps(payload), encoding="utf-8")
    destination = ProjectStore(tmp_path / "destination", "project-a")
    with pytest.raises(TransferError, match="record counts do not match"):
        import_store(tampered, destination)
    assert destination.list_coverage() == []
    assert destination.list_measurements() == []


def test_sqlite_database_can_be_copied_and_reopened_independently(tmp_path):
    import shutil

    root = tmp_path / "source"
    root.mkdir()
    (root / "file.bin").write_bytes(b"portable")
    registry = parse_registry({
        "schema_version": "0.1",
        "project_id": "project-a",
        "sources": [source(root)],
    })
    original = ProjectStore(tmp_path / "original-db", "project-a")
    ScanRunner(
        registry,
        gate(),
        {"filesystem": FilesystemAdapter(tmp_path, allowed_root=tmp_path)},
        original,
    ).run("fs-local", "operator-a")

    destination_root = tmp_path / "independent-environment"
    destination_root.mkdir()
    shutil.copy2(original.path, destination_root / "project-a.sqlite3")
    restored = ProjectStore(destination_root, "project-a")
    assert restored.list_coverage() == original.list_coverage()
    assert restored.list_measurements() == original.list_measurements()



def test_authorization_revocation_during_scan_discards_partial_measurements(tmp_path):
    root = tmp_path / "source"
    (root / "nested").mkdir(parents=True)
    (root / "first.bin").write_bytes(b"first")
    (root / "nested" / "second.bin").write_bytes(b"second")
    registry = parse_registry({
        "schema_version": "0.1",
        "project_id": "project-a",
        "sources": [source(root)],
    })
    calls = {"count": 0}

    def authorizer(*args):
        calls["count"] += 1
        return calls["count"] < 3

    store = ProjectStore(tmp_path / "db", "project-a")
    outcome = ScanRunner(
        registry,
        ExecutionGate(
            ControlState(
                True,
                frozenset({"project-a"}),
                frozenset({("project-a", "storage")}),
                frozenset({("project-a", "fs-local")}),
            ),
            authorizer,
        ),
        {"filesystem": FilesystemAdapter(tmp_path, allowed_root=tmp_path)},
        store,
    ).run("fs-local", "operator-a")
    assert outcome.coverage_state == "NOT_AUTHORIZED"
    assert outcome.reason_code == "authorization_revoked"
    assert store.list_measurements() == []


def test_timeout_budget_is_enforced_before_page_work(monkeypatch, tmp_path):
    from ecoscan.models import ScanBudget

    clock = iter([10.0, 12.0])
    monkeypatch.setattr("ecoscan.contracts.time.monotonic", lambda: next(clock))
    guard = BudgetGuard(
        ScanBudget(max_pages=10, max_items=10, timeout_seconds=1, max_duration_seconds=1)
    )
    with pytest.raises(BudgetExceeded, match="time budget"):
        guard.consume_page()
