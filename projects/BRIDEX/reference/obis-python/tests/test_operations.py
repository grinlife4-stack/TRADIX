from concurrent.futures import ThreadPoolExecutor
import hashlib

import pytest

from obis_bridge.operations import (
    IdempotencyConflict,
    InvalidOperationTransition,
    OperationLedger,
    OperationNotFound,
)


def ledger(tmp_path):
    return OperationLedger(tmp_path / "operations.sqlite3")


def reserve(store, *, operation_id="op-1", key="key-1", request_hash="a" * 64, now=1000):
    return store.reserve(
        operation_id=operation_id, idempotency_key=key, request_hash=request_hash,
        peer_id="peer:caller", principal_ref="principal:caller",
        capability_id="records.write", capability_version="1.0",
        expires_at=now + 300, now=now,
    )


def test_reserve_is_durable_and_duplicate_returns_existing_record(tmp_path):
    store = ledger(tmp_path)
    first, created = reserve(store)
    restarted = ledger(tmp_path)
    second, created_again = reserve(restarted)
    assert created is True
    assert created_again is False
    assert first["operation_id"] == second["operation_id"] == "op-1"
    assert second["state"] == "ACCEPTED"


def test_same_idempotency_key_with_different_request_is_conflict(tmp_path):
    store = ledger(tmp_path)
    reserve(store)
    with pytest.raises(IdempotencyConflict):
        reserve(store, request_hash="b" * 64)


def test_same_idempotency_key_with_different_operation_id_is_conflict(tmp_path):
    store = ledger(tmp_path)
    reserve(store)
    with pytest.raises(IdempotencyConflict):
        reserve(store, operation_id="op-2")


def test_operation_id_cannot_be_reused_for_another_key(tmp_path):
    store = ledger(tmp_path)
    reserve(store)
    with pytest.raises(IdempotencyConflict):
        reserve(store, key="key-2")


def test_concurrent_duplicate_reservation_creates_exactly_one_operation(tmp_path):
    store = ledger(tmp_path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: reserve(store), range(8)))
    assert sum(1 for _, created in results if created) == 1
    assert len({record["operation_id"] for record, _ in results}) == 1


def test_state_transitions_and_result_recovery(tmp_path):
    store = ledger(tmp_path)
    reserve(store)
    store.transition("op-1", "RUNNING", now=1001)
    result = store.transition("op-1", "SUCCEEDED", result={"written": True}, now=1002)
    assert result["state"] == "SUCCEEDED"
    assert result["result"] == {"written": True}
    with pytest.raises(InvalidOperationTransition):
        store.transition("op-1", "RUNNING", now=1003)


def test_failed_and_rejected_states_require_stable_failure_code(tmp_path):
    store = ledger(tmp_path)
    reserve(store)
    with pytest.raises(ValueError):
        store.transition("op-1", "REJECTED")
    result = store.transition("op-1", "REJECTED", failure_code="authorization.denied")
    assert result["state"] == "REJECTED"


def test_crash_recovery_marks_running_as_unknown_and_never_reexecutes(tmp_path):
    store = ledger(tmp_path)
    reserve(store)
    store.transition("op-1", "RUNNING", now=1001)
    restarted = ledger(tmp_path)
    assert restarted.recover_running_as_unknown(now=1002) == 1
    record = restarted.get(
        "op-1", peer_id="peer:caller", principal_ref="principal:caller",
        capability_id="records.write", capability_version="1.0",
    )
    assert record["state"] == "UNKNOWN"
    with pytest.raises(InvalidOperationTransition):
        restarted.transition("op-1", "RUNNING", now=1003)


def test_status_query_is_scoped_to_authenticated_identity(tmp_path):
    store = ledger(tmp_path)
    reserve(store)
    with pytest.raises(OperationNotFound):
        store.get(
            "op-1", peer_id="peer:attacker", principal_ref="principal:caller",
            capability_id="records.write", capability_version="1.0",
        )


def test_invalid_hash_and_memory_database_are_rejected(tmp_path):
    with pytest.raises(ValueError):
        OperationLedger(":memory:")
    store = ledger(tmp_path)
    with pytest.raises(ValueError):
        reserve(store, request_hash="not-a-hash")


def test_operation_result_must_be_json_and_exactly_one_result_form(tmp_path):
    store = ledger(tmp_path)
    reserve(store)
    store.transition("op-1", "RUNNING")
    with pytest.raises(ValueError):
        store.transition("op-1", "SUCCEEDED", result={"ok": True}, result_ref="ref")
    with pytest.raises(ValueError):
        store.transition("op-1", "SUCCEEDED", result={"bad": float("nan")})
