"""Real PostgreSQL integration test for the complete durable-ledger lifecycle.

Runs only against the disposable PostgreSQL service created by GitHub Actions.
"""
from __future__ import annotations

import hashlib
import os
import uuid

import pytest

from tradix.factory.postgres_ledger import LedgerPersistenceError, PostgresTaskLedger


DSN = os.getenv("TRADIX_TEST_DATABASE_URL")


@pytest.mark.skipif(not DSN, reason="requires disposable PostgreSQL CI service")
def test_real_postgres_full_task_lifecycle_and_readback():
    import psycopg

    ledger = PostgresTaskLedger.from_dsn(DSN)
    nonce = uuid.uuid4().hex
    task_key = f"e2e-{nonce}"
    task_args = {
        "task_key": task_key,
        "title": "PostgreSQL end-to-end lifecycle",
        "request_text": "Exercise task creation, attempt, evidence, transitions and durable read-back.",
        "acceptance_criteria": ("all three evidence records are persisted", "task reaches verified after deployed-test"),
        "risk_class": "low",
        "approval_required": False,
        "approval_scope": {},
    }

    task_id = ledger.create_task(**task_args)
    assert ledger.create_task(**task_args) == task_id

    attempt_key = f"e2e-attempt-{nonce}"
    attempt_id = ledger.create_attempt(
        task_id,
        idempotency_key=attempt_key,
        worker_role="implementer",
        branch_name="ci/postgres-ledger-e2e",
        metadata={"run": "disposable-postgres"},
    )
    assert ledger.create_attempt(
        task_id,
        idempotency_key=attempt_key,
        worker_role="implementer",
        branch_name="ci/postgres-ledger-e2e",
        metadata={"run": "disposable-postgres"},
    ) == attempt_id

    worker_id = f"postgres-ledger-integration:{nonce}"
    fencing_token, _expires_at = ledger.acquire_task_lease(
        task_id, attempt_id, worker_id=worker_id, ttl_seconds=60
    )

    def transition(state: str, suffix: str) -> int:
        return ledger.transition_task_fenced(
            task_id,
            attempt_id,
            worker_id=worker_id,
            fencing_token=fencing_token,
            target_state=state,
            event_type=f"task.{state}",
            actor_type="system",
            actor_ref="postgres-ledger-integration-test",
            idempotency_key=f"e2e-transition-{nonce}-{suffix}",
            payload={"integration_test": True},
        )

    planned_seq = transition("planned", "planned")
    assert ledger.transition_task_fenced(
        task_id,
        attempt_id,
        worker_id=worker_id,
        fencing_token=fencing_token,
        target_state="planned",
        event_type="task.planned",
        actor_type="system",
        actor_ref="postgres-ledger-integration-test",
        idempotency_key=f"e2e-transition-{nonce}-planned",
        payload={"integration_test": True},
    ) == planned_seq

    transition("implementing", "implementing")
    transition("testing", "testing")

    test_report = b'{"result":"passed","suite":"integration"}'
    ledger.record_evidence_fenced(
        task_id,
        attempt_id,
        worker_id=worker_id,
        fencing_token=fencing_token,
        artifact_type="test-report",
        object_uri=f"ci://tradix/{nonce}/test-report.json",
        sha256=hashlib.sha256(test_report).hexdigest(),
        byte_size=len(test_report),
        content_type="application/json",
        evidence_type="test_report",
        description="Real PostgreSQL integration test report",
        metadata={"test": "full-lifecycle"},
    )
    transition("review", "review")

    review_report = b'{"review":"passed","scope":"bounded"}'
    ledger.record_evidence_fenced(
        task_id,
        attempt_id,
        worker_id=worker_id,
        fencing_token=fencing_token,
        artifact_type="review-report",
        object_uri=f"ci://tradix/{nonce}/review-report.json",
        sha256=hashlib.sha256(review_report).hexdigest(),
        byte_size=len(review_report),
        content_type="application/json",
        evidence_type="review_report",
        description="Real PostgreSQL integration review report",
        metadata={"test": "full-lifecycle"},
    )
    transition("candidate", "candidate")
    transition("deployed_test", "deployed-test")

    health_report = b'{"health":"passed","service":"disposable-postgres"}'
    ledger.record_evidence_fenced(
        task_id,
        attempt_id,
        worker_id=worker_id,
        fencing_token=fencing_token,
        artifact_type="health-check",
        object_uri=f"ci://tradix/{nonce}/health-check.json",
        sha256=hashlib.sha256(health_report).hexdigest(),
        byte_size=len(health_report),
        content_type="application/json",
        evidence_type="health_check",
        description="Real PostgreSQL integration health check",
        metadata={"test": "full-lifecycle"},
    )
    assert ledger.finish_attempt_fenced(
        task_id, attempt_id, worker_id=worker_id, fencing_token=fencing_token, outcome="succeeded"
    ) == "succeeded"
    transition("verified", "verified")
    assert ledger.release_task_lease(
        task_id, attempt_id, worker_id=worker_id, fencing_token=fencing_token
    ) is True
    with pytest.raises(LedgerPersistenceError):
        ledger.renew_task_lease(
            task_id, attempt_id, worker_id=worker_id, fencing_token=fencing_token
        )

    # A TRADIX runtime must not be able to create an attempt for the fixed
    # info_engine fixture task seeded by the SQL isolation suite.
    with pytest.raises(LedgerPersistenceError):
        ledger.create_attempt(
            "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
            idempotency_key=f"cross-project-{nonce}",
            worker_role="implementer",
        )

    # Read back the committed projection and its immutable event/evidence trail
    # through the same restricted product login, not the PostgreSQL admin.
    with psycopg.connect(DSN) as connection:
        connection.execute("SET ROLE factory_runtime")
        with connection.cursor() as cursor:
            cursor.execute("SELECT session_user::text, current_user::text")
            assert cursor.fetchone() == ("factory_rt_tradix", "factory_runtime")

            cursor.execute(
                "SELECT status, current_attempt FROM factory.tasks WHERE task_id = %s",
                (task_id,),
            )
            assert cursor.fetchone() == ("verified", 1)

            cursor.execute(
                "SELECT to_state FROM factory.task_events WHERE task_id = %s ORDER BY event_seq",
                (task_id,),
            )
            assert [row[0] for row in cursor.fetchall()] == [
                "planned", "implementing", "testing", "review", "candidate", "deployed_test", "verified"
            ]

            cursor.execute(
                "SELECT evidence_type FROM factory.task_evidence WHERE task_id = %s ORDER BY evidence_type",
                (task_id,),
            )
            assert [row[0] for row in cursor.fetchall()] == ["health_check", "review_report", "test_report"]

            cursor.execute(
                "SELECT status FROM factory.task_attempts WHERE attempt_id = %s AND task_id = %s",
                (attempt_id, task_id),
            )
            assert cursor.fetchone() == ("succeeded",)

            cursor.execute(
                "SELECT count(*) FROM factory.tasks WHERE task_id = %s",
                ("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",),
            )
            assert cursor.fetchone() == (0,)
