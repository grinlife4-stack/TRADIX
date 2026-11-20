"""Durable owner-local operation ledger for OBIS 0.2.

The ledger provides atomic idempotency reservation and conservative crash recovery.
It does not by itself make an external provider's side effects exactly-once.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any


class OperationLedgerError(Exception):
    """Base class for durable operation ledger failures."""


class IdempotencyConflict(OperationLedgerError):
    """An operation or idempotency key was reused with different identity/data."""


class OperationNotFound(OperationLedgerError):
    """No operation exists in the authenticated caller's scope."""


class InvalidOperationTransition(OperationLedgerError):
    """A requested state transition is not permitted."""


TERMINAL_STATES = frozenset({"SUCCEEDED", "FAILED", "REJECTED", "UNKNOWN", "CANCELLED", "EXPIRED"})


class OperationLedger:
    """SQLite-backed operation ledger owned by the capability-providing Bridge.

    Every mutating operation uses BEGIN IMMEDIATE and FULL synchronous commits.
    The database path must be on persistent storage controlled by the owner.
    """

    def __init__(self, database_path: str | Path):
        raw = str(database_path).strip()
        if not raw or raw == ":memory:":
            raise ValueError("operation ledger requires a persistent filesystem database")
        self.database_path = Path(raw).expanduser().resolve()
        if not self.database_path.parent.is_dir():
            raise ValueError("operation ledger parent directory must already exist")
        self._lock = threading.RLock()
        connection = self._connect()
        try:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS obis_operations (
                    operation_id TEXT PRIMARY KEY,
                    peer_id TEXT NOT NULL,
                    principal_ref TEXT NOT NULL,
                    capability_id TEXT NOT NULL,
                    capability_version TEXT NOT NULL,
                    idempotency_key_hash TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN (
                        'ACCEPTED','RUNNING','SUCCEEDED','FAILED','REJECTED',
                        'UNKNOWN','CANCELLED','EXPIRED'
                    )),
                    result_json TEXT,
                    result_ref TEXT,
                    failure_code TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    UNIQUE (
                        peer_id, principal_ref, capability_id,
                        capability_version, idempotency_key_hash
                    )
                );
                CREATE INDEX IF NOT EXISTS obis_operations_scope
                ON obis_operations(peer_id, principal_ref, capability_id, capability_version);
                CREATE INDEX IF NOT EXISTS obis_operations_state
                ON obis_operations(state);
            """)
        finally:
            connection.close()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self.database_path), timeout=10.0, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout = 10000")
        db.execute("PRAGMA journal_mode = WAL")
        db.execute("PRAGMA synchronous = FULL")
        db.execute("PRAGMA foreign_keys = ON")
        return db

    @staticmethod
    def _validate_text(name: str, value: str) -> None:
        if not isinstance(value, str) or not value or len(value) > 200:
            raise ValueError(f"{name} must be a non-empty string of at most 200 characters")

    @staticmethod
    def _validate_hash(request_hash: str) -> None:
        if not isinstance(request_hash, str) or len(request_hash) != 64:
            raise ValueError("request_hash must be a lowercase SHA-256 hex digest")
        try:
            bytes.fromhex(request_hash)
        except ValueError as exc:
            raise ValueError("request_hash must be a lowercase SHA-256 hex digest") from exc
        if request_hash.lower() != request_hash:
            raise ValueError("request_hash must use lowercase hexadecimal")

    @staticmethod
    def _key_hash(key: str) -> str:
        OperationLedger._validate_text("idempotency_key", key)
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    @staticmethod
    def _record(row: sqlite3.Row) -> dict[str, Any]:
        result = json.loads(row["result_json"]) if row["result_json"] is not None else None
        return {
            "operation_id": row["operation_id"],
            "peer_id": row["peer_id"],
            "principal_ref": row["principal_ref"],
            "capability_id": row["capability_id"],
            "capability_version": row["capability_version"],
            "request_hash": row["request_hash"],
            "state": row["state"],
            "result": result,
            "result_ref": row["result_ref"],
            "failure_code": row["failure_code"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "expires_at": row["expires_at"],
        }

    def reserve(
        self, *, operation_id: str, idempotency_key: str, request_hash: str,
        peer_id: str, principal_ref: str, capability_id: str,
        capability_version: str, expires_at: float, now: float | None = None,
    ) -> tuple[dict[str, Any], bool]:
        """Atomically reserve an operation. Returns (record, newly_created)."""
        for name, value in (
            ("operation_id", operation_id), ("peer_id", peer_id),
            ("principal_ref", principal_ref), ("capability_id", capability_id),
            ("capability_version", capability_version),
        ):
            self._validate_text(name, value)
        self._validate_hash(request_hash)
        key_hash = self._key_hash(idempotency_key)
        now = time.time() if now is None else now
        if isinstance(now, bool) or not isinstance(now, (int, float)) or not math.isfinite(now):
            raise ValueError("now must be a finite timestamp")
        if isinstance(expires_at, bool) or not isinstance(expires_at, (int, float)) or not math.isfinite(expires_at) or expires_at <= now:
            raise ValueError("expires_at must be a finite future timestamp")

        scope = (peer_id, principal_ref, capability_id, capability_version)
        with self._lock:
            db = self._connect()
            try:
                db.execute("BEGIN IMMEDIATE")
                by_key = db.execute(
                    """SELECT * FROM obis_operations
                    WHERE peer_id=? AND principal_ref=? AND capability_id=?
                    AND capability_version=? AND idempotency_key_hash=?""",
                    (*scope, key_hash),
                ).fetchone()
                by_id = db.execute(
                    "SELECT * FROM obis_operations WHERE operation_id=?", (operation_id,)
                ).fetchone()
                if by_key is not None:
                    existing = self._record(by_key)
                    if (
                        existing["operation_id"] != operation_id
                        or existing["request_hash"] != request_hash
                    ):
                        raise IdempotencyConflict("idempotency key is already bound to another operation or request")
                    if by_id is not None and by_id["operation_id"] != existing["operation_id"]:
                        raise IdempotencyConflict("operation ID conflicts with an existing ledger record")
                    db.execute("COMMIT")
                    return existing, False
                if by_id is not None:
                    raise IdempotencyConflict("operation ID is already bound to another request identity")
                db.execute(
                    """INSERT INTO obis_operations (
                        operation_id, peer_id, principal_ref, capability_id,
                        capability_version, idempotency_key_hash, request_hash,
                        state, created_at, updated_at, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'ACCEPTED', ?, ?, ?)""",
                    (operation_id, *scope, key_hash, request_hash, float(now), float(now), float(expires_at)),
                )
                row = db.execute(
                    "SELECT * FROM obis_operations WHERE operation_id=?", (operation_id,)
                ).fetchone()
                db.execute("COMMIT")
                return self._record(row), True
            except Exception:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
            finally:
                db.close()

    def transition(
        self, operation_id: str, state: str, *, result: dict[str, Any] | None = None,
        result_ref: str | None = None, failure_code: str | None = None,
        now: float | None = None,
    ) -> dict[str, Any]:
        if state not in {"RUNNING", "SUCCEEDED", "FAILED", "REJECTED", "UNKNOWN", "CANCELLED", "EXPIRED"}:
            raise ValueError("unsupported operation state")
        if result is not None and not isinstance(result, dict):
            raise ValueError("result must be an object or None")
        if result_ref is not None and (not isinstance(result_ref, str) or not result_ref):
            raise ValueError("result_ref must be a non-empty string or None")
        if failure_code is not None and (not isinstance(failure_code, str) or not failure_code):
            raise ValueError("failure_code must be a non-empty string or None")
        if state == "SUCCEEDED" and (result is None) == (result_ref is None):
            raise ValueError("SUCCEEDED requires exactly one of result or result_ref")
        if state in {"FAILED", "REJECTED"} and failure_code is None:
            raise ValueError("FAILED and REJECTED require failure_code")
        if state not in {"SUCCEEDED"} and (result is not None or result_ref is not None):
            raise ValueError("only SUCCEEDED may contain a result")
        now = time.time() if now is None else now
        result_json = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) if result is not None else None

        with self._lock:
            db = self._connect()
            try:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT * FROM obis_operations WHERE operation_id=?", (operation_id,)).fetchone()
                if row is None:
                    raise OperationNotFound(operation_id)
                current = row["state"]
                allowed = {"ACCEPTED": {"RUNNING", "REJECTED", "EXPIRED"}, "RUNNING": {"SUCCEEDED", "FAILED", "UNKNOWN", "CANCELLED"}}
                if state not in allowed.get(current, set()):
                    raise InvalidOperationTransition(f"cannot transition {current} to {state}")
                db.execute(
                    """UPDATE obis_operations SET state=?, result_json=?, result_ref=?,
                    failure_code=?, updated_at=? WHERE operation_id=?""",
                    (state, result_json, result_ref, failure_code, float(now), operation_id),
                )
                updated = db.execute("SELECT * FROM obis_operations WHERE operation_id=?", (operation_id,)).fetchone()
                db.execute("COMMIT")
                return self._record(updated)
            except Exception:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
            finally:
                db.close()

    def get(
        self, operation_id: str, *, peer_id: str, principal_ref: str,
        capability_id: str, capability_version: str,
    ) -> dict[str, Any]:
        row_scope = (peer_id, principal_ref, capability_id, capability_version, operation_id)
        db = self._connect()
        try:
            row = db.execute(
                """SELECT * FROM obis_operations WHERE peer_id=? AND principal_ref=?
                AND capability_id=? AND capability_version=? AND operation_id=?""",
                row_scope,
            ).fetchone()
            if row is None:
                raise OperationNotFound(operation_id)
            return self._record(row)
        finally:
            db.close()

    def recover_running_as_unknown(self, now: float | None = None) -> int:
        """Conservatively mark interrupted RUNNING operations UNKNOWN on startup."""
        now = time.time() if now is None else now
        with self._lock:
            db = self._connect()
            try:
                db.execute("BEGIN IMMEDIATE")
                cursor = db.execute(
                    """UPDATE obis_operations SET state='UNKNOWN', updated_at=?
                    WHERE state='RUNNING'""",
                    (float(now),),
                )
                count = cursor.rowcount
                db.execute("COMMIT")
                return count
            except Exception:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
            finally:
                db.close()
