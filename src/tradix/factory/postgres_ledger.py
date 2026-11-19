"""Narrow PostgreSQL client for the TRADIX durable factory ledger.

The database remains authoritative for project identity, permissions, lifecycle
transitions, approval gates, idempotency, and evidence requirements. This client
only calls named SECURITY DEFINER functions; it exposes no arbitrary SQL surface.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable, Mapping
from uuid import UUID


class LedgerPersistenceError(RuntimeError):
    """A durable ledger operation failed; underlying database details are hidden."""


_TASK_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$")
_IDEMPOTENCY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,254}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_WORKER_ROLES = {"planner", "implementer", "tester", "reviewer", "release", "observer"}
_TASK_STATES = {
    "queued", "planned", "implementing", "testing", "review", "candidate",
    "deployed_test", "verified", "blocked", "failed", "cancelled",
}
_ACTOR_TYPES = {"system", "agent", "github"}


def _json_object(value: Mapping[str, Any], name: str) -> str:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    try:
        return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must contain JSON-compatible values") from exc


def _uuid(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a UUID string")
    try:
        return str(UUID(value))
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"{name} must be a UUID string") from exc


def _required_text(value: str, name: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{name} must contain 1..{maximum} characters")
    return value


class PostgresTaskLedger:
    """Calls the controlled factory ledger functions using an injected connection factory."""

    def __init__(self, connection_factory: Callable[[], Any]) -> None:
        if not callable(connection_factory):
            raise TypeError("connection_factory must be callable")
        self._connection_factory = connection_factory

    @classmethod
    def from_dsn(cls, dsn: str, *, connect_timeout: int = 5) -> "PostgresTaskLedger":
        """Create a lazy psycopg 3 connection factory; no connection occurs at construction."""
        if not isinstance(dsn, str) or not dsn.strip():
            raise ValueError("dsn must be a non-empty string")
        if isinstance(connect_timeout, bool) or not isinstance(connect_timeout, int) or not 1 <= connect_timeout <= 30:
            raise ValueError("connect_timeout must be an integer from 1 to 30")
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("Install TRADIX with the postgres extra to use from_dsn") from exc
        def connect_as_runtime():
            connection = psycopg.connect(dsn, connect_timeout=connect_timeout)
            try:
                # Activate only the restricted runtime group. session_user remains
                # the product-specific LOGIN used by database isolation policies.
                connection.execute("SET ROLE factory_runtime")
            except Exception:
                connection.close()
                raise
            return connection

        return cls(connect_as_runtime)

    def _scalar(self, operation: str, statement: str, parameters: tuple[Any, ...]) -> Any:
        try:
            with self._connection_factory() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(statement, parameters)
                    row = cursor.fetchone()
                    if row is None:
                        raise LedgerPersistenceError(f"{operation} returned no result")
                    return row[0]
        except LedgerPersistenceError:
            raise
        except Exception as exc:
            # Do not leak DSNs, SQL parameter values, or provider-specific error detail.
            raise LedgerPersistenceError(f"{operation} failed; transaction was rolled back") from exc

    def create_task(
        self,
        *,
        task_key: str,
        title: str,
        request_text: str,
        acceptance_criteria: tuple[str, ...],
        risk_class: str = "low",
        approval_required: bool = False,
        approval_scope: Mapping[str, Any] | None = None,
    ) -> str:
        _required_text(task_key, "task_key", 120)
        if not _TASK_KEY.fullmatch(task_key):
            raise ValueError("task_key contains unsupported characters")
        _required_text(title, "title", 160)
        _required_text(request_text, "request_text", 12000)
        if not isinstance(acceptance_criteria, tuple) or not 1 <= len(acceptance_criteria) <= 30:
            raise ValueError("acceptance_criteria must contain 1..30 strings")
        for criterion in acceptance_criteria:
            _required_text(criterion, "acceptance criterion", 500)
        if risk_class not in {"low", "medium", "high", "critical"}:
            raise ValueError("risk_class is invalid")
        if not isinstance(approval_required, bool):
            raise ValueError("approval_required must be a boolean")
        if risk_class in {"high", "critical"} and not approval_required:
            raise ValueError("high and critical risk tasks require approval")
        scope = _json_object(approval_scope or {}, "approval_scope")
        criteria = json.dumps(list(acceptance_criteria), ensure_ascii=False, separators=(",", ":"))
        value = self._scalar(
            "create_task",
            "SELECT factory.create_task(%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb)",
            (task_key, title, request_text, criteria, risk_class, approval_required, scope),
        )
        return str(value)

    def create_attempt(
        self,
        task_id: str,
        *,
        idempotency_key: str,
        worker_role: str = "implementer",
        branch_name: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> str:
        task = _uuid(task_id, "task_id")
        _required_text(idempotency_key, "idempotency_key", 255)
        if not _IDEMPOTENCY.fullmatch(idempotency_key):
            raise ValueError("idempotency_key contains unsupported characters")
        if worker_role not in _WORKER_ROLES:
            raise ValueError("worker_role is not allowlisted")
        if branch_name is not None:
            _required_text(branch_name, "branch_name", 255)
        meta = _json_object(metadata or {}, "metadata")
        value = self._scalar(
            "create_attempt",
            "SELECT factory.create_task_attempt(%s::uuid,%s,%s,%s,%s::jsonb)",
            (task, idempotency_key, worker_role, branch_name, meta),
        )
        return str(value)

    def transition_task(
        self,
        task_id: str,
        target_state: str,
        *,
        event_type: str,
        actor_type: str,
        actor_ref: str,
        idempotency_key: str,
        attempt_id: str | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> int:
        task = _uuid(task_id, "task_id")
        if target_state not in _TASK_STATES:
            raise ValueError("target_state is invalid")
        _required_text(event_type, "event_type", 100)
        if actor_type not in _ACTOR_TYPES:
            raise ValueError("actor_type must be system, agent, or github")
        _required_text(actor_ref, "actor_ref", 200)
        _required_text(idempotency_key, "idempotency_key", 255)
        if not _IDEMPOTENCY.fullmatch(idempotency_key):
            raise ValueError("idempotency_key contains unsupported characters")
        attempt = _uuid(attempt_id, "attempt_id") if attempt_id is not None else None
        body = _json_object(payload or {}, "payload")
        value = self._scalar(
            "transition_task",
            "SELECT factory.transition_task(%s::uuid,%s,%s,%s,%s,%s,%s::uuid,%s::jsonb)",
            (task, target_state, event_type, actor_type, actor_ref, idempotency_key, attempt, body),
        )
        return int(value)

    def record_evidence(
        self,
        task_id: str,
        attempt_id: str,
        *,
        artifact_type: str,
        object_uri: str,
        sha256: str,
        byte_size: int,
        content_type: str = "application/octet-stream",
        evidence_type: str,
        description: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> str:
        task = _uuid(task_id, "task_id")
        attempt = _uuid(attempt_id, "attempt_id")
        _required_text(artifact_type, "artifact_type", 80)
        _required_text(object_uri, "object_uri", 2048)
        if not isinstance(sha256, str) or not _SHA256.fullmatch(sha256):
            raise ValueError("sha256 must be 64 lowercase hexadecimal characters")
        if isinstance(byte_size, bool) or not isinstance(byte_size, int) or byte_size < 0:
            raise ValueError("byte_size must be a non-negative integer")
        _required_text(content_type, "content_type", 255)
        _required_text(evidence_type, "evidence_type", 100)
        if not isinstance(description, str) or len(description) > 4000:
            raise ValueError("description must be at most 4000 characters")
        meta = _json_object(metadata or {}, "metadata")
        value = self._scalar(
            "record_evidence",
            "SELECT factory.record_task_evidence(%s::uuid,%s::uuid,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
            (task, attempt, artifact_type, object_uri, sha256, byte_size, content_type,
             evidence_type, description, meta),
        )
        return str(value)

    def finish_attempt(self, task_id: str, attempt_id: str, *, outcome: str) -> str:
        task = _uuid(task_id, "task_id")
        attempt = _uuid(attempt_id, "attempt_id")
        if outcome not in {"succeeded", "failed"}:
            raise ValueError("outcome must be succeeded or failed")
        value = self._scalar(
            "finish_attempt",
            "SELECT factory.finish_task_attempt(%s::uuid,%s::uuid,%s)",
            (task, attempt, outcome),
        )
        return str(value)
