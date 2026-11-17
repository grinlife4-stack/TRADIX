"""Append-only, hash-chained audit ledger for CPIIE.

The SQLite table is tamper-evident against accidental/ordinary row changes, not
against an operator who controls the database file. Independent authenticity
comes only from exporting and signing the chain head with an externally managed
signer/key, then retaining that signed export outside this database.
"""
from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Protocol


GENESIS_HASH = "0" * 64
LEDGER_SCHEMA = "cpiie-audit-ledger-v1"
EXPORT_SCHEMA = "cpiie-signed-audit-export-v1"


class AuditIntegrityError(ValueError):
    """Raised when audit evidence is incomplete, altered, or unverifiable."""


class AuditSigner(Protocol):
    """Externally managed signing adapter; private keys must never enter this DB."""

    def sign(self, message: bytes) -> bytes:
        ...

    def verify(self, message: bytes, signature: bytes) -> bool:
        ...


def canonical_json(value: Any) -> bytes:
    """Deterministic UTF-8 JSON encoding for the ledger's constrained data model."""
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("audit data must be finite, JSON-serializable values") from exc


def _aware_timestamp(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("occurred_at must be a timezone-aware ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("occurred_at must be a timezone-aware ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("occurred_at must include a timezone offset")
    return parsed.astimezone(timezone.utc).isoformat()


def _event_hash(event: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(event)).hexdigest()


def verify_events(events: list[dict[str, Any]]) -> str:
    """Verify sequence, canonical payloads, links and event hashes; return head."""
    previous = GENESIS_HASH
    for expected_sequence, event in enumerate(events, start=1):
        if not isinstance(event, dict):
            raise AuditIntegrityError("event record is not an object")
        required = {
            "sequence", "schema", "event_type", "occurred_at",
            "payload", "previous_hash", "event_hash",
        }
        if set(event) != required:
            raise AuditIntegrityError("event fields are missing or unexpected")
        if event["sequence"] != expected_sequence:
            raise AuditIntegrityError("sequence gap, duplicate, or reordered event")
        if event["schema"] != LEDGER_SCHEMA:
            raise AuditIntegrityError("unsupported event schema")
        if event["previous_hash"] != previous:
            raise AuditIntegrityError("previous-hash link mismatch")
        if not isinstance(event["payload"], dict):
            raise AuditIntegrityError("event payload must be an object")
        normalized_time = _aware_timestamp(event["occurred_at"])
        if normalized_time != event["occurred_at"]:
            raise AuditIntegrityError("event timestamp is not canonical UTC")
        body = {key: event[key] for key in required if key != "event_hash"}
        if _event_hash(body) != event["event_hash"]:
            raise AuditIntegrityError("event hash mismatch")
        previous = event["event_hash"]
    return previous


class AuditLedger:
    """SQLite-backed append-only hash chain with externally signed exports."""

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS cpiie_audit_events (
                sequence INTEGER PRIMARY KEY,
                schema TEXT NOT NULL,
                event_type TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL UNIQUE
            )
        """)
        self.connection.executescript("""
            CREATE TRIGGER IF NOT EXISTS cpiie_audit_no_update
            BEFORE UPDATE ON cpiie_audit_events
            BEGIN SELECT RAISE(ABORT, 'audit ledger is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS cpiie_audit_no_delete
            BEFORE DELETE ON cpiie_audit_events
            BEGIN SELECT RAISE(ABORT, 'audit ledger is append-only'); END;
        """)
        self.connection.commit()

    def events(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM cpiie_audit_events ORDER BY sequence"
        ).fetchall()
        result = []
        for row in rows:
            try:
                payload = json.loads(row["payload_json"])
            except json.JSONDecodeError as exc:
                raise AuditIntegrityError("stored audit payload is invalid JSON") from exc
            result.append({
                "sequence": row["sequence"], "schema": row["schema"],
                "event_type": row["event_type"], "occurred_at": row["occurred_at"],
                "payload": payload, "previous_hash": row["previous_hash"],
                "event_hash": row["event_hash"],
            })
        return result

    def append(
        self, event_type: str, payload: dict[str, Any],
        occurred_at: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(event_type, str) or not event_type.strip():
            raise ValueError("event_type is required")
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        # Validate JSON compatibility before opening a write transaction.
        payload_json = canonical_json(payload).decode("utf-8")
        timestamp = _aware_timestamp(
            occurred_at or datetime.now(timezone.utc).isoformat()
        )
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            rows = self.events()
            head = verify_events(rows)
            sequence = len(rows) + 1
            body = {
                "sequence": sequence, "schema": LEDGER_SCHEMA,
                "event_type": event_type.strip(), "occurred_at": timestamp,
                "payload": json.loads(payload_json), "previous_hash": head,
            }
            digest = _event_hash(body)
            self.connection.execute(
                """INSERT INTO cpiie_audit_events
                   (sequence, schema, event_type, occurred_at, payload_json,
                    previous_hash, event_hash) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (sequence, LEDGER_SCHEMA, body["event_type"], timestamp,
                 payload_json, head, digest),
            )
            self.connection.commit()
            return {**body, "event_hash": digest}
        except Exception:
            self.connection.rollback()
            raise

    def verify(self) -> str:
        return verify_events(self.events())

    def signed_export(self, signer: AuditSigner) -> dict[str, Any]:
        if signer is None:
            raise AuditIntegrityError("external signing key is required")
        events = self.events()
        head = verify_events(events)
        document = {
            "schema": EXPORT_SCHEMA,
            "event_count": len(events),
            "head_hash": head,
            "events": events,
        }
        message = canonical_json(document)
        signature = signer.sign(message)
        if not isinstance(signature, bytes) or not signature:
            raise AuditIntegrityError("external signer returned no signature")
        return {
            "document": document,
            "signature_base64": base64.b64encode(signature).decode("ascii"),
        }


def verify_signed_export(
    export: dict[str, Any], signer: AuditSigner,
    expected_prior_head: str | None = None,
) -> str:
    """Verify signature and chain. expected_prior_head enables external anti-replay anchoring."""
    if signer is None:
        raise AuditIntegrityError("trusted external verification key is unavailable")
    if not isinstance(export, dict) or set(export) != {"document", "signature_base64"}:
        raise AuditIntegrityError("signed export envelope is malformed")
    document = export["document"]
    if not isinstance(document, dict) or set(document) != {
        "schema", "event_count", "head_hash", "events"
    }:
        raise AuditIntegrityError("signed export document is malformed")
    if document["schema"] != EXPORT_SCHEMA or not isinstance(document["events"], list):
        raise AuditIntegrityError("unsupported signed export schema")
    events = document["events"]
    if document["event_count"] != len(events):
        raise AuditIntegrityError("signed export event count mismatch")
    head = verify_events(events)
    if head != document["head_hash"]:
        raise AuditIntegrityError("signed export head hash mismatch")
    if expected_prior_head is not None:
        if expected_prior_head == GENESIS_HASH:
            pass
        elif expected_prior_head not in [event["event_hash"] for event in events]:
            raise AuditIntegrityError("export does not extend the independently retained prior anchor")
    try:
        signature = base64.b64decode(export["signature_base64"], validate=True)
    except (ValueError, TypeError) as exc:
        raise AuditIntegrityError("signature encoding is invalid") from exc
    if not signature or not signer.verify(canonical_json(document), signature):
        raise AuditIntegrityError("signed export signature is invalid")
    return head
