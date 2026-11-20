import json
import sqlite3
from pathlib import Path

import pytest

from ecoscan.controls import ControlState, ExecutionGate
from ecoscan.registry import RegistryError, parse_registry
from ecoscan.store import ProjectStore, StoreError


def source(source_id="fs-main", subsystem_id="storage"):
    return {
        "source_id": source_id,
        "owner_id": "owner-a",
        "operator_id": "operator-a",
        "subsystem_id": subsystem_id,
        "source_type": "filesystem",
        "locator": "/not-scanned-by-these-tests",
        "adapter_id": "filesystem",
        "adapter_version": "0.1.0",
        "credential_ref": None,
        "enabled": True,
        "scope_tags": ["local"],
        "budget": {
            "max_pages": 20,
            "max_items": 1000,
            "timeout_seconds": 10,
            "max_duration_seconds": 60,
        },
        "expected_measurements": ["logical_bytes", "file_count"],
        "retention_policy": {"history_days": 30, "evidence_days": 0},
        "created_at": "2026-11-20T09:00:00Z",
        "updated_at": "2026-11-20T09:00:00Z",
    }


def registry(*sources):
    return {"schema_version": "0.1", "project_id": "project-a", "sources": list(sources)}


def test_registry_rejects_duplicate_source_ids():
    with pytest.raises(RegistryError, match="unique"):
        parse_registry(registry(source(), source()))


def test_registry_rejects_unknown_fields_and_invalid_subsystem_ids():
    with pytest.raises(RegistryError, match="unknown fields"):
        parse_registry(registry({**source(), "application_key": "secret"}))
    with pytest.raises(RegistryError, match="identifier"):
        parse_registry(registry({**source(), "subsystem_id": "../outside"}))


def test_registry_rejects_naive_or_inverted_timestamps():
    with pytest.raises(RegistryError, match="timezone"):
        parse_registry(registry({**source(), "created_at": "2026-11-20T09:00:00"}))
    with pytest.raises(RegistryError, match="precede"):
        parse_registry(registry({
            **source(),
            "created_at": "2026-11-20T10:00:00Z",
            "updated_at": "2026-11-20T09:00:00Z",
        }))


def test_registry_rejects_non_string_measurement_kind():
    with pytest.raises(RegistryError, match="expected_measurements"):
        parse_registry(registry({**source(), "expected_measurements": [{"kind": "logical_bytes"}]}))


def test_registry_loads_from_disk(tmp_path):
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(registry(source())), encoding="utf-8")
    parsed = parse_registry(json.loads(path.read_text(encoding="utf-8")))
    assert parsed.project_id == "project-a"
    assert parsed.sources[0].source_id == "fs-main"


def test_controls_fail_closed_at_every_level():
    parsed = parse_registry(registry(source()))
    item = parsed.sources[0]
    denied = ExecutionGate(ControlState()).evaluate(parsed, item, "operator-a")
    assert (denied.allowed, denied.coverage_state, denied.reason_code) == (False, "DISABLED", "global_disabled")

    global_only = ControlState(global_enabled=True)
    denied = ExecutionGate(global_only, lambda *_: True).evaluate(parsed, item, "operator-a")
    assert denied.reason_code == "project_disabled"

    project = ControlState(global_enabled=True, enabled_projects=frozenset({"project-a"}))
    denied = ExecutionGate(project, lambda *_: True).evaluate(parsed, item, "operator-a")
    assert denied.reason_code == "subsystem_disabled"

    subsystem = ControlState(
        global_enabled=True,
        enabled_projects=frozenset({"project-a"}),
        enabled_subsystems=frozenset({("project-a", "storage")}),
    )
    denied = ExecutionGate(subsystem, lambda *_: True).evaluate(parsed, item, "operator-a")
    assert denied.reason_code == "source_disabled"


def test_controls_require_explicit_owner_operator_authorization():
    parsed = parse_registry(registry(source()))
    item = parsed.sources[0]
    controls = ControlState(
        global_enabled=True,
        enabled_projects=frozenset({"project-a"}),
        enabled_subsystems=frozenset({("project-a", "storage")}),
        enabled_sources=frozenset({("project-a", "fs-main")}),
    )
    denied = ExecutionGate(controls).evaluate(parsed, item, "operator-a")
    assert denied.coverage_state == "NOT_AUTHORIZED"
    allowed = ExecutionGate(controls, lambda actor, project, owner, operator, source_id:
                            (actor, project, owner, operator, source_id) ==
                            ("operator-a", "project-a", "owner-a", "operator-a", "fs-main"))
    assert allowed.evaluate(parsed, item, "operator-a").allowed is True


def measurement(project_id="project-a", source_id="fs-main", measurement_id="m-1"):
    return {
        "schema_version": "0.1",
        "measurement_id": measurement_id,
        "project_id": project_id,
        "source_id": source_id,
        "kind": "logical_bytes",
        "value": 12,
        "unit": "byte",
        "measured_at": "2026-11-20T09:00:00Z",
        "source_timestamp": None,
        "method": "filesystem-stat",
        "adapter_id": "filesystem",
        "adapter_version": "0.1.0",
        "coverage_state": "COMPLETE",
        "confidence": "HIGH",
        "limitations": [],
        "evidence_ref": None,
        "checkpoint_ref": None,
    }


def coverage(project_id="project-a", source_id="fs-main", scan_id="scan-1"):
    return {
        "schema_version": "0.1",
        "scan_id": scan_id,
        "project_id": project_id,
        "source_id": source_id,
        "requested_scope": "source:fs-main",
        "coverage_state": "COMPLETE",
        "started_at": "2026-11-20T09:00:00Z",
        "finished_at": "2026-11-20T09:00:01Z",
        "actor_id": "operator-a",
        "adapter_id": "filesystem",
        "adapter_version": "0.1.0",
        "items_seen": 1,
        "pages_seen": 1,
        "reason_code": None,
        "limitations": [],
        "checkpoint_ref": None,
    }


def test_project_store_isolated_and_append_only(tmp_path):
    store_a = ProjectStore(tmp_path, "project-a")
    store_b = ProjectStore(tmp_path, "project-b")
    store_a.append_scan(coverage(), [measurement()])
    assert len(store_a.list_measurements()) == 1
    assert store_b.list_measurements() == []
    with pytest.raises(StoreError, match="does not match"):
        store_a.append_scan(coverage(project_id="project-b"), [measurement(project_id="project-b")])


def test_project_store_transaction_rolls_back_mismatched_measurement(tmp_path):
    store = ProjectStore(tmp_path, "project-a")
    with pytest.raises(StoreError, match="must match"):
        store.append_scan(
            coverage(),
            [measurement(), measurement(source_id="another-source", measurement_id="m-2")],
        )
    assert store.list_coverage() == []
    assert store.list_measurements() == []

    with pytest.raises(sqlite3.IntegrityError):
        store.append_scan(
            coverage(scan_id="scan-2"),
            [measurement(measurement_id="duplicate"), measurement(measurement_id="duplicate")],
        )
    assert store.list_coverage() == []
    assert store.list_measurements() == []


def test_project_store_rejects_duplicate_measurement_and_scan_ids(tmp_path):
    store = ProjectStore(tmp_path, "project-a")
    store.append_scan(coverage(), [measurement()])
    with pytest.raises(sqlite3.IntegrityError):
        store.append_scan(coverage(), [measurement()])
    assert len(store.list_coverage()) == 1
    assert len(store.list_measurements()) == 1


def test_project_checkpoints_are_separate_and_replaceable(tmp_path):
    store = ProjectStore(tmp_path, "project-a")
    store.save_checkpoint("fs-main", "scan-1", {"cursor": "a"}, "2026-11-20T09:00:00Z")
    store.save_checkpoint("fs-main", "scan-1", {"cursor": "b"}, "2026-11-20T09:01:00Z")
    assert store.load_checkpoint("fs-main", "scan-1") == {"cursor": "b"}
    assert store.load_checkpoint("fs-main", "scan-2") is None


def test_standalone_schemas_match_canonical_contract_files():
    repo_root = Path(__file__).resolve().parents[3]
    package_schema_root = Path(__file__).resolve().parents[1] / "src" / "ecoscan" / "schemas"
    canonical_schema_root = repo_root / "standards" / "ecoscan" / "0.1"
    for name in (
        "source-registry.schema.json",
        "measurement.schema.json",
        "coverage.schema.json",
        "export-manifest.schema.json",
    ):
        assert (package_schema_root / name).read_bytes() == (canonical_schema_root / name).read_bytes()


def test_cli_validates_registry_without_scanning(tmp_path, capsys):
    from ecoscan.cli import main

    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps(registry(source())), encoding="utf-8")
    assert main(["validate-registry", str(registry_path)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "VALID"
    assert output["source_count"] == 1


def test_standalone_package_has_no_tradix_runtime_imports():
    source_root = Path(__file__).resolve().parents[1] / "src" / "ecoscan"
    for source_file in source_root.rglob("*.py"):
        code = source_file.read_text(encoding="utf-8")
        assert "from tradix" not in code
        assert "import tradix" not in code
