from __future__ import annotations

import hashlib

import pytest

from ecoscan.store import ProjectStore, StoreError


def _intent():
    return {
        "scan_id": "scan-001",
        "operation_id": "operation-001",
        "idempotency_key": "idem-001",
        "source_id": "source-a",
        "peer_id": "peer:owner",
        "principal_ref": "principal:ecoscan",
        "capability_id": "ecoscan.inventory.read",
        "capability_version": "1.0",
        "resource": {"project_id": "project-a", "source_id": "source-a"},
        "payload_sha256": hashlib.sha256(b'{"project_id":"project-a","source_id":"source-a"}').hexdigest(),
        "request_hash": hashlib.sha256(b"request-projection").hexdigest(),
        "created_at": "2026-11-20T20:00:00Z",
    }


def test_operation_intent_is_durable_and_contains_no_credentials(tmp_path):
    store = ProjectStore(tmp_path, "project-a")
    record = store.create_operation_intent(**_intent())

    reopened = ProjectStore(tmp_path, "project-a")
    recovered = reopened.get_operation_intent("scan-001")

    assert record == recovered
    assert recovered["state"] == "PREPARED"
    assert recovered["operation_id"] == "operation-001"
    assert recovered["idempotency_key"] == "idem-001"
    assert "secret" not in recovered
    assert "credential" not in recovered


def test_unresolved_intents_are_listed_without_reissuing_operations(tmp_path):
    store = ProjectStore(tmp_path, "project-a")
    store.create_operation_intent(**_intent())

    pending = store.list_unresolved_operation_intents()

    assert len(pending) == 1
    assert pending[0]["state"] == "PREPARED"
    assert pending[0]["operation_id"] == "operation-001"


def test_intent_state_requires_explicit_reconciliation(tmp_path):
    store = ProjectStore(tmp_path, "project-a")
    store.create_operation_intent(**_intent())

    indeterminate = store.transition_operation_intent(
        "scan-001", "INDETERMINATE", "2026-11-20T20:01:00Z"
    )
    assert indeterminate["state"] == "INDETERMINATE"
    assert len(store.list_unresolved_operation_intents()) == 1

    succeeded = store.transition_operation_intent(
        "scan-001", "RECONCILED_SUCCEEDED", "2026-11-20T20:02:00Z"
    )
    assert succeeded["state"] == "RECONCILED_SUCCEEDED"
    assert store.list_unresolved_operation_intents() == []

    with pytest.raises(StoreError):
        store.transition_operation_intent(
            "scan-001", "INDETERMINATE", "2026-11-20T20:03:00Z"
        )


def test_intent_rejects_cross_project_resource_and_malformed_hash(tmp_path):
    store = ProjectStore(tmp_path, "project-a")
    invalid = _intent()
    invalid["resource"] = {"project_id": "project-b", "source_id": "source-a"}
    with pytest.raises(StoreError):
        store.create_operation_intent(**invalid)

    invalid = _intent()
    invalid["payload_sha256"] = "not-a-hash"
    with pytest.raises(StoreError):
        store.create_operation_intent(**invalid)


def test_reconciliation_event_and_intent_transition_are_atomic_and_append_only(tmp_path):
    store = ProjectStore(tmp_path, "project-a")
    store.create_operation_intent(**_intent())
    store.transition_operation_intent("scan-001", "INDETERMINATE", "2026-11-20T20:01:00Z")

    store.append_operation_reconciliation(
        reconciliation_id="reconcile-001",
        scan_id="scan-001",
        source_id="source-a",
        outcome="SUCCEEDED",
        recorded_at="2026-11-20T20:02:00Z",
        result={"measurements": {"logical_bytes": 42}},
    )
    assert store.get_operation_intent("scan-001")["state"] == "RECONCILED_SUCCEEDED"
    assert store.list_operation_reconciliations()[0]["result"] == {
        "measurements": {"logical_bytes": 42}
    }
    with pytest.raises(StoreError):
        store.append_operation_reconciliation(
            reconciliation_id="reconcile-001",
            scan_id="scan-001",
            source_id="source-a",
            outcome="SUCCEEDED",
            recorded_at="2026-11-20T20:03:00Z",
            result={"measurements": {"logical_bytes": 99}},
        )
    assert len(store.list_operation_reconciliations()) == 1
    assert store.get_operation_intent("scan-001")["state"] == "RECONCILED_SUCCEEDED"


def test_reconciliation_and_intent_survive_export_import(tmp_path):
    from ecoscan.transfer import export_store, import_store

    source_store = ProjectStore(tmp_path / "source", "project-a")
    source_store.create_operation_intent(**_intent())
    source_store.transition_operation_intent("scan-001", "INDETERMINATE", "2026-11-20T20:01:00Z")
    source_store.append_operation_reconciliation(
        reconciliation_id="reconcile-001",
        scan_id="scan-001",
        source_id="source-a",
        outcome="SUCCEEDED",
        recorded_at="2026-11-20T20:02:00Z",
        result={"measurements": {"logical_bytes": 42}},
    )
    export_path = export_store(source_store, tmp_path / "exports", "json")[0]

    destination = ProjectStore(tmp_path / "destination", "project-a")
    inserted = import_store(export_path, destination)
    assert inserted == 2
    assert destination.get_operation_intent("scan-001")["state"] == "RECONCILED_SUCCEEDED"
    assert destination.list_operation_reconciliations()[0]["result"] == {
        "measurements": {"logical_bytes": 42}
    }
    assert import_store(export_path, destination) == 0
