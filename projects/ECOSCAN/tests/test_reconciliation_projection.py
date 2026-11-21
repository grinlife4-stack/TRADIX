from __future__ import annotations

from ecoscan.controls import ControlState, ExecutionGate
from ecoscan.models import ProjectRegistry, RetentionPolicy, ScanBudget, SourceDescriptor
from ecoscan.runner import ScanRunner
from ecoscan.store import ProjectStore
from ecoscan.transfer import export_store, import_store


def _source():
    return SourceDescriptor(
        source_id="remote-storage",
        owner_id="owner-a",
        operator_id="operator-a",
        subsystem_id="storage",
        source_type="obis_bridge",
        locator="peer:inventory-bridge",
        adapter_id="obis_bridge",
        adapter_version="0.1.0",
        enabled=True,
        scope_tags=("inventory",),
        budget=ScanBudget(max_pages=10, max_items=100, timeout_seconds=10, max_duration_seconds=10),
        expected_measurements=("logical_bytes", "file_count"),
        retention_policy=RetentionPolicy(history_days=30, evidence_days=30),
        created_at="2026-11-20T00:00:00Z",
        updated_at="2026-11-20T00:00:00Z",
    )


def _prepared_store(tmp_path):
    store = ProjectStore(tmp_path, "project-a")
    coverage = {
        "schema_version": "0.2",
        "scan_id": "scan-original",
        "project_id": "project-a",
        "source_id": "remote-storage",
        "requested_scope": "source:remote-storage",
        "coverage_state": "INDETERMINATE",
        "started_at": "2026-11-21T06:00:00Z",
        "finished_at": "2026-11-21T06:00:05Z",
        "actor_id": "operator-a",
        "adapter_id": "obis_bridge",
        "adapter_version": "0.1.0",
        "items_seen": 0,
        "pages_seen": 0,
        "reason_code": "transport_outcome_unknown",
        "limitations": ["Remote operation outcome was unknown at timeout."],
        "checkpoint_ref": None,
    }
    store.append_scan(coverage, [])
    store.create_operation_intent(
        scan_id="scan-original",
        operation_id="operation-original",
        idempotency_key="idem-original",
        source_id="remote-storage",
        peer_id="peer:inventory-bridge",
        principal_ref="principal:ecoscan",
        capability_id="ecoscan.inventory.read",
        capability_version="1.0",
        resource={"project_id": "project-a", "source_id": "remote-storage"},
        payload_sha256="a" * 64,
        request_hash="b" * 64,
        created_at="2026-11-21T06:00:00Z",
    )
    store.transition_operation_intent(
        "scan-original", "INDETERMINATE", "2026-11-21T06:00:05Z"
    )
    store.append_operation_reconciliation(
        reconciliation_id="reconciliation-original",
        scan_id="scan-original",
        source_id="remote-storage",
        outcome="SUCCEEDED",
        recorded_at="2026-11-21T06:02:00Z",
        result={
            "project_id": "project-a",
            "source_id": "remote-storage",
            "coverage_state": "COMPLETE",
            "items_seen": 2,
            "pages_seen": 1,
            "measurements": {"logical_bytes": 4096, "file_count": 2},
            "source_timestamp": "2026-11-21T05:59:00Z",
            "limitations": [],
            "evidence_ref": "bridge-evidence-001",
        },
    )
    return store


def _runner(store):
    source = _source()
    registry = ProjectRegistry("project-a", (source,))
    gate = ExecutionGate(
        ControlState(
            global_enabled=True,
            enabled_projects=frozenset({"project-a"}),
            enabled_subsystems=frozenset({("project-a", "storage")}),
            enabled_sources=frozenset({("project-a", "remote-storage")}),
        ),
        lambda *args: True,
    )
    return ScanRunner(registry, gate, {}, store)


def test_successful_reconciliation_projects_standard_measurements_idempotently(tmp_path):
    store = _prepared_store(tmp_path)
    runner = _runner(store)

    first = runner.project_reconciled_measurements("remote-storage")
    second = runner.project_reconciled_measurements("remote-storage")

    assert first == [{
        "reconciliation_id": "reconciliation-original",
        "state": "PROJECTED",
        "measurements_inserted": 2,
    }]
    assert second == [{
        "reconciliation_id": "reconciliation-original",
        "state": "PROJECTED",
        "measurements_inserted": 0,
    }]
    measurements = store.list_measurements("remote-storage")
    assert {item["kind"]: item["value"] for item in measurements} == {
        "logical_bytes": 4096,
        "file_count": 2,
    }
    assert all(item["scan_id"] == "scan-original" for item in measurements)
    assert all(item["coverage_state"] == "COMPLETE" for item in measurements)
    assert all(item["confidence"] == "UNVERIFIED" for item in measurements)
    assert all(item["method"].startswith("obis_v0.2_status_reconciliation:") for item in measurements)
    assert len(store.list_reconciliation_measurement_links()) == 2
    assert store.list_coverage()[0]["coverage_state"] == "INDETERMINATE"


def test_projection_export_import_preserves_measurement_lineage_and_is_idempotent(tmp_path):
    source_store = _prepared_store(tmp_path / "source")
    _runner(source_store).project_reconciled_measurements("remote-storage")
    export_path = export_store(source_store, tmp_path / "exports", "jsonl")[0]

    destination = ProjectStore(tmp_path / "destination", "project-a")
    inserted = import_store(export_path, destination)

    assert inserted == 7
    assert len(destination.list_measurements()) == 2
    assert len(destination.list_reconciliation_measurement_links()) == 2
    assert destination.list_coverage()[0]["coverage_state"] == "INDETERMINATE"
    assert import_store(export_path, destination) == 0


def test_projection_rejects_event_without_original_indeterminate_coverage(tmp_path):
    store = _prepared_store(tmp_path)
    with store._connect() as db:
        db.execute(
            "UPDATE coverage SET coverage_state='COMPLETE' WHERE scan_id='scan-original'"
        )
    result = _runner(store).project_reconciled_measurements("remote-storage")
    assert result[0]["state"] == "PROJECTION_PENDING"
    assert store.list_measurements() == []



def test_projection_recovers_after_restart_between_event_commit_and_projection(tmp_path):
    store = _prepared_store(tmp_path)
    # Simulate the durable reconciliation event being committed, followed by
    # process termination before any Measurement projection begins.
    assert store.list_operation_reconciliations()[0]["outcome"] == "SUCCEEDED"
    assert store.list_measurements() == []

    reopened = ProjectStore(tmp_path, "project-a")
    result = _runner(reopened).project_reconciled_measurements("remote-storage")

    assert result == [{
        "reconciliation_id": "reconciliation-original",
        "state": "PROJECTED",
        "measurements_inserted": 2,
    }]
    assert len(reopened.list_measurements()) == 2
    assert len(reopened.list_reconciliation_measurement_links()) == 2
    assert reopened.list_coverage()[0]["coverage_state"] == "INDETERMINATE"


def test_projection_rolls_back_measurements_and_links_as_one_unit(tmp_path):
    store = _prepared_store(tmp_path)
    original_values = store._measurement_values
    calls = 0

    def fail_on_second_measurement(record):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated process failure during projection")
        return original_values(record)

    store._measurement_values = fail_on_second_measurement
    failed = _runner(store).project_reconciled_measurements("remote-storage")

    assert failed[0]["state"] == "PROJECTION_PENDING"
    assert store.list_measurements() == []
    assert store.list_reconciliation_measurement_links() == []
    assert store.list_operation_reconciliations()[0]["outcome"] == "SUCCEEDED"
    assert store.list_coverage()[0]["coverage_state"] == "INDETERMINATE"

    store._measurement_values = original_values
    recovered = _runner(ProjectStore(tmp_path, "project-a")).project_reconciled_measurements("remote-storage")
    assert recovered[0]["state"] == "PROJECTED"
    assert recovered[0]["measurements_inserted"] == 2
    assert len(store.list_measurements()) == 2
    assert len(store.list_reconciliation_measurement_links()) == 2


def test_concurrent_projection_is_idempotent_across_store_instances(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    store_a = _prepared_store(tmp_path)
    store_b = ProjectStore(tmp_path, "project-a")
    runner_a = _runner(store_a)
    runner_b = _runner(store_b)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda runner: runner.project_reconciled_measurements("remote-storage"),
            (runner_a, runner_b),
        ))

    assert all(result[0]["state"] == "PROJECTED" for result in results)
    assert sum(result[0]["measurements_inserted"] for result in results) == 2
    assert len(store_a.list_measurements()) == 2
    assert len(store_a.list_reconciliation_measurement_links()) == 2
    assert store_a.list_coverage()[0]["coverage_state"] == "INDETERMINATE"
