from contextlib import contextmanager

import pytest

from tradix.factory.postgres_ledger import (
    LedgerPersistenceError,
    PostgresTaskLedger,
)


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, statement, parameters):
        self.connection.calls.append((statement, parameters))
        if self.connection.error:
            raise RuntimeError("secret DSN and provider detail")
    def fetchone(self):
        return (self.connection.result,)


class FakeConnection:
    def __init__(self, result="result", error=False):
        self.result = result
        self.error = error
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return FakeCursor(self)


def make_ledger(connection):
    return PostgresTaskLedger(lambda: connection)


def test_create_task_calls_only_named_database_function():
    connection = FakeConnection("task-uuid")
    result = make_ledger(connection).create_task(
        task_key="first-task",
        title="First task",
        request_text="Do bounded work",
        acceptance_criteria=("tests pass",),
    )
    statement, params = connection.calls[0]
    assert result == "task-uuid"
    assert "factory.create_task" in statement
    assert params[0:3] == ("first-task", "First task", "Do bounded work")
    assert params[3] == '["tests pass"]'


def test_create_task_rejects_critical_without_approval_before_io():
    connection = FakeConnection()
    with pytest.raises(ValueError, match="require approval"):
        make_ledger(connection).create_task(
            task_key="critical-task", title="Critical", request_text="x",
            acceptance_criteria=("x",), risk_class="critical",
        )
    assert connection.calls == []


def test_create_attempt_uses_allowlisted_role_and_uuid():
    connection = FakeConnection("attempt-uuid")
    result = make_ledger(connection).create_attempt(
        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        idempotency_key="attempt-1",
        worker_role="tester",
        metadata={"source": "ci"},
    )
    assert result == "attempt-uuid"
    assert "factory.create_task_attempt" in connection.calls[0][0]


def test_create_attempt_rejects_arbitrary_worker_role():
    connection = FakeConnection()
    with pytest.raises(ValueError, match="allowlisted"):
        make_ledger(connection).create_attempt(
            "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            idempotency_key="attempt-1",
            worker_role="shell",
        )
    assert connection.calls == []


def test_transition_calls_controlled_function_and_returns_sequence():
    connection = FakeConnection(42)
    result = make_ledger(connection).transition_task(
        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "planned",
        event_type="task.planned",
        actor_type="system",
        actor_ref="unit-test",
        idempotency_key="transition-1",
    )
    assert result == 42
    assert "factory.transition_task" in connection.calls[0][0]


def test_transition_rejects_human_actor_and_bad_uuid_before_io():
    connection = FakeConnection()
    with pytest.raises(ValueError, match="actor_type"):
        make_ledger(connection).transition_task(
            "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "planned",
            event_type="task.planned", actor_type="human",
            actor_ref="person", idempotency_key="transition-1",
        )
    with pytest.raises(ValueError, match="UUID"):
        make_ledger(connection).transition_task(
            "not-a-uuid", "planned", event_type="task.planned",
            actor_type="system", actor_ref="unit-test", idempotency_key="transition-1",
        )
    assert connection.calls == []


def test_record_evidence_checks_hash_and_size_before_io():
    connection = FakeConnection("artifact-uuid")
    ledger = make_ledger(connection)
    with pytest.raises(ValueError, match="sha256"):
        ledger.record_evidence(
            "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
            artifact_type="test-report", object_uri="s3://bucket/key",
            sha256="bad", byte_size=10, evidence_type="test_report",
        )
    assert connection.calls == []
    result = ledger.record_evidence(
        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        artifact_type="test-report", object_uri="s3://bucket/key",
        sha256="a" * 64, byte_size=10, evidence_type="test_report",
    )
    assert result == "artifact-uuid"
    assert "factory.record_task_evidence" in connection.calls[0][0]


def test_finish_attempt_is_allowlisted():
    connection = FakeConnection("succeeded")
    result = make_ledger(connection).finish_attempt(
        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        outcome="succeeded",
    )
    assert result == "succeeded"
    assert "factory.finish_task_attempt" in connection.calls[0][0]


def test_database_errors_are_sanitized():
    connection = FakeConnection(error=True)
    with pytest.raises(LedgerPersistenceError, match="transaction was rolled back") as error:
        make_ledger(connection).create_task(
            task_key="first-task", title="First task", request_text="Do work",
            acceptance_criteria=("tests pass",),
        )
    assert "secret DSN" not in str(error.value)
