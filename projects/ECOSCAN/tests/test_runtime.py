import json
import sqlite3
import time
from pathlib import Path

import pytest

from ecoscan.contracts import AdapterResult
from ecoscan.controls import ControlState, ExecutionGate
from ecoscan.registry import RegistryError, parse_registry
from ecoscan.runner import ScanRunner
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


class FakeAdapter:
    adapter_id = "filesystem"
    version = "0.1.0"

    def __init__(self, result=None, error=None, version=None, overrun=False):
        self.result = result
        self.error = error
        self.calls = 0
        self.validations = 0
        self.overrun = overrun
        if version is not None:
            self.version = version

    def validate_config(self, source_descriptor):
        self.validations += 1

    def scan(self, context):
        self.calls += 1
        context.guard.consume_page()
        context.guard.consume_item()
        if self.overrun:
            context.guard.consume_item()
        if self.error is not None:
            raise self.error
        return self.result or AdapterResult(
            coverage_state="COMPLETE",
            measurements=(measurement(),),
            items_seen=1,
            pages_seen=1,
            checkpoint={"cursor": "next-entry"},
        )


def enabled_gate(authorizer=lambda *_: True):
    return ExecutionGate(
        ControlState(
            global_enabled=True,
            enabled_projects=frozenset({"project-a"}),
            enabled_subsystems=frozenset({("project-a", "storage")}),
            enabled_sources=frozenset({("project-a", "fs-main")}),
        ),
        authorizer,
    )


def test_runner_executes_exact_registered_source_and_commits_checkpoint_atomically(tmp_path):
    parsed = parse_registry(registry(source()))
    store = ProjectStore(tmp_path, "project-a")
    adapter = FakeAdapter()
    runner = ScanRunner(parsed, enabled_gate(), {"filesystem": adapter}, store)

    outcome = runner.run("fs-main", "operator-a")

    assert outcome.coverage_state == "COMPLETE"
    assert outcome.measurements_written == 1
    assert adapter.validations == 1
    assert adapter.calls == 1
    assert len(store.list_measurements("fs-main")) == 1
    assert len(store.list_coverage("fs-main")) == 1
    assert store.load_checkpoint("fs-main", outcome.scan_id) == {"cursor": "next-entry"}


def test_runner_records_disabled_without_invoking_adapter(tmp_path):
    parsed = parse_registry(registry(source()))
    store = ProjectStore(tmp_path, "project-a")
    adapter = FakeAdapter()
    runner = ScanRunner(parsed, ExecutionGate(ControlState()), {"filesystem": adapter}, store)

    outcome = runner.run("fs-main", "operator-a")

    assert outcome.coverage_state == "DISABLED"
    assert adapter.calls == 0
    assert store.list_measurements() == []
    assert store.list_coverage()[0]["reason_code"] == "global_disabled"


def test_runner_records_not_authorized_without_invoking_adapter(tmp_path):
    parsed = parse_registry(registry(source()))
    store = ProjectStore(tmp_path, "project-a")
    adapter = FakeAdapter()
    runner = ScanRunner(parsed, enabled_gate(authorizer=None), {"filesystem": adapter}, store)

    outcome = runner.run("fs-main", "operator-a")

    assert outcome.coverage_state == "NOT_AUTHORIZED"
    assert adapter.calls == 0
    assert store.list_measurements() == []


def test_runner_rejects_adapter_version_mismatch(tmp_path):
    parsed = parse_registry(registry(source()))
    store = ProjectStore(tmp_path, "project-a")
    adapter = FakeAdapter(version="9.9.9")
    runner = ScanRunner(parsed, enabled_gate(), {"filesystem": adapter}, store)

    outcome = runner.run("fs-main", "operator-a")

    assert outcome.coverage_state == "FAILED"
    assert outcome.reason_code == "adapter_version_mismatch"
    assert adapter.calls == 0


def test_runner_rejects_cross_project_measurement_and_records_failure(tmp_path):
    parsed = parse_registry(registry(source()))
    store = ProjectStore(tmp_path, "project-a")
    invalid = measurement(project_id="project-b")
    adapter = FakeAdapter(result=AdapterResult("COMPLETE", (invalid,), 1, 1))
    runner = ScanRunner(parsed, enabled_gate(), {"filesystem": adapter}, store)

    outcome = runner.run("fs-main", "operator-a")

    assert outcome.coverage_state == "FAILED"
    assert outcome.reason_code == "adapter_contract_violation"
    assert store.list_measurements() == []
    assert store.list_coverage()[0]["coverage_state"] == "FAILED"


def test_runner_rejects_late_empty_result_after_absolute_deadline(tmp_path):
    parsed = parse_registry(registry({
        **source(),
        "budget": {
            "max_pages": 1,
            "max_items": 1,
            "timeout_seconds": 1,
            "max_duration_seconds": 1,
        },
    }))
    store = ProjectStore(tmp_path, "project-a")

    class SlowEmptyAdapter(FakeAdapter):
        def scan(self, context):
            self.calls += 1
            context.guard.consume_page()
            time.sleep(1.05)
            return AdapterResult("COMPLETE", (), 0, 1)

    adapter = SlowEmptyAdapter()
    runner = ScanRunner(parsed, enabled_gate(), {"filesystem": adapter}, store)
    outcome = runner.run("fs-main", "operator-a")

    assert outcome.coverage_state == "FAILED"
    assert outcome.reason_code == "budget_exhausted"
    assert store.list_measurements() == []
    assert store.list_coverage()[0]["coverage_state"] == "FAILED"
    assert store.list_coverage()[0]["items_seen"] == 0
    assert store.list_coverage()[0]["pages_seen"] == 1


def test_runner_rejects_malformed_source_timestamp_without_measurement_commit(tmp_path):
    parsed = parse_registry(registry(source()))
    store = ProjectStore(tmp_path, "project-a")
    invalid = {**measurement(), "source_timestamp": "not-a-timestamp"}
    adapter = FakeAdapter(result=AdapterResult("COMPLETE", (invalid,), 1, 1))
    runner = ScanRunner(parsed, enabled_gate(), {"filesystem": adapter}, store)

    outcome = runner.run("fs-main", "operator-a")

    assert outcome.coverage_state == "FAILED"
    assert outcome.reason_code == "adapter_contract_violation"
    assert store.list_measurements() == []
    assert store.list_coverage()[0]["coverage_state"] == "FAILED"


def test_runner_records_budget_exhaustion_and_does_not_commit_measurements(tmp_path):
    parsed = parse_registry(registry({
        **source(),
        "budget": {
            "max_pages": 1,
            "max_items": 1,
            "timeout_seconds": 10,
            "max_duration_seconds": 60,
        },
    }))
    store = ProjectStore(tmp_path, "project-a")
    adapter = FakeAdapter(overrun=True)
    runner = ScanRunner(parsed, enabled_gate(), {"filesystem": adapter}, store)

    outcome = runner.run("fs-main", "operator-a")

    assert outcome.coverage_state == "FAILED"
    assert outcome.reason_code == "budget_exhausted"
    assert store.list_measurements() == []
    assert store.list_coverage()[0]["items_seen"] == 1


def test_runner_records_adapter_exception_without_leaking_exception_text(tmp_path):
    parsed = parse_registry(registry(source()))
    store = ProjectStore(tmp_path, "project-a")
    adapter = FakeAdapter(error=RuntimeError("secret token should not be persisted"))
    runner = ScanRunner(parsed, enabled_gate(), {"filesystem": adapter}, store)

    outcome = runner.run("fs-main", "operator-a")

    assert outcome.coverage_state == "FAILED"
    assert outcome.reason_code == "adapter_execution_failed"
    assert "secret token" not in str(store.list_coverage())


def test_store_scan_and_checkpoint_are_one_transaction(tmp_path):
    store = ProjectStore(tmp_path, "project-a")
    with pytest.raises(sqlite3.IntegrityError):
        store.append_scan(
            coverage(scan_id="atomic-scan"),
            [measurement(measurement_id="same"), measurement(measurement_id="same")],
            checkpoint={"cursor": "must-rollback"},
            checkpoint_updated_at="2026-11-20T09:00:02Z",
        )
    assert store.list_coverage() == []
    assert store.list_measurements() == []
    assert store.load_checkpoint("fs-main", "atomic-scan") is None


def test_authorizer_exceptions_and_non_boolean_grants_fail_closed():
    parsed = parse_registry(registry(source()))
    item = parsed.sources[0]
    controls = ControlState(
        global_enabled=True,
        enabled_projects=frozenset({"project-a"}),
        enabled_subsystems=frozenset({("project-a", "storage")}),
        enabled_sources=frozenset({("project-a", "fs-main")}),
    )
    raising = ExecutionGate(controls, lambda *_: (_ for _ in ()).throw(RuntimeError("auth backend down")))
    non_boolean = ExecutionGate(controls, lambda *_: "true")
    assert raising.evaluate(parsed, item, "operator-a").coverage_state == "NOT_AUTHORIZED"
    assert non_boolean.evaluate(parsed, item, "operator-a").coverage_state == "NOT_AUTHORIZED"


def test_runner_rejects_measurement_unit_mismatch(tmp_path):
    parsed = parse_registry(registry(source()))
    store = ProjectStore(tmp_path, "project-a")
    invalid = {**measurement(), "unit": "object"}
    adapter = FakeAdapter(result=AdapterResult("COMPLETE", (invalid,), 1, 1))
    runner = ScanRunner(parsed, enabled_gate(), {"filesystem": adapter}, store)

    outcome = runner.run("fs-main", "operator-a")

    assert outcome.coverage_state == "FAILED"
    assert outcome.reason_code == "adapter_contract_violation"
    assert store.list_measurements() == []


def test_runner_marks_missing_adapter_not_configured(tmp_path):
    parsed = parse_registry(registry(source()))
    store = ProjectStore(tmp_path, "project-a")
    runner = ScanRunner(parsed, enabled_gate(), {}, store)

    outcome = runner.run("fs-main", "operator-a")

    assert outcome.coverage_state == "NOT_CONFIGURED"
    assert outcome.reason_code == "adapter_not_registered"
    assert store.list_measurements() == []


def test_runner_rejects_non_string_measurement_confidence(tmp_path):
    parsed = parse_registry(registry(source()))
    store = ProjectStore(tmp_path, "project-a")
    invalid = {**measurement(), "confidence": ["HIGH"]}
    adapter = FakeAdapter(result=AdapterResult("COMPLETE", (invalid,), 1, 1))
    runner = ScanRunner(parsed, enabled_gate(), {"filesystem": adapter}, store)

    outcome = runner.run("fs-main", "operator-a")

    assert outcome.coverage_state == "FAILED"
    assert outcome.reason_code == "adapter_contract_violation"
    assert store.list_measurements() == []


def test_runner_rechecks_owner_operator_authorization_before_each_page(tmp_path):
    parsed = parse_registry(registry(source()))
    store = ProjectStore(tmp_path, "project-a")
    checks = {"count": 0}

    def revoke_after_initial_gate(*_):
        checks["count"] += 1
        return checks["count"] == 1

    adapter = FakeAdapter()
    runner = ScanRunner(parsed, enabled_gate(revoke_after_initial_gate), {"filesystem": adapter}, store)

    outcome = runner.run("fs-main", "operator-a")

    assert outcome.coverage_state == "NOT_AUTHORIZED"
    assert outcome.reason_code == "authorization_revoked"
    assert checks["count"] == 2
    assert adapter.calls == 1
    assert store.list_measurements() == []
    assert store.list_coverage()[0]["pages_seen"] == 0
