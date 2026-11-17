"""Persistent, fail-closed registry for reusable TRADIX capabilities.

This is a local SQLite prototype. It records proposals and append-only status
events; it does not import, execute, publish, or deploy capability code.
"""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
_REQUIRED_REVIEW_FLAGS = (
    "security_passed",
    "license_cleared",
    "cost_assessed",
    "tests_passed",
    "compatibility_passed",
    "owner_approved",
)


class PromotionBlocked(ValueError):
    """Raised when a capability does not satisfy promotion gates."""


@dataclass(frozen=True)
class Capability:
    capability_id: str
    version: str
    origin_project: str
    owner: str
    scope: str
    summary: str
    interface: str
    tests_ref: str
    changelog: str
    compatibility: str
    deprecation: str
    evidence_ref: str


@dataclass(frozen=True)
class CapabilityReview:
    security_passed: bool
    license_cleared: bool
    cost_assessed: bool
    tests_passed: bool
    compatibility_passed: bool
    owner_approved: bool
    external_project_use_case: str = ""
    factory_need_reference: str = ""


class CapabilityRegistry:
    """SQLite-backed capability proposal and promotion ledger.

    Each capability version is immutable. Status changes are represented by
    additional events, rather than updates to the capability record.
    """

    def __init__(self, database: str | Path) -> None:
        self.database = str(database)
        if self.database != ":memory:":
            Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS capabilities (
                    capability_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (capability_id, version)
                );

                CREATE TABLE IF NOT EXISTS capability_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    capability_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (
                        status IN ('proposed', 'accepted', 'rejected', 'deprecated')
                    ),
                    actor TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    FOREIGN KEY (capability_id, version)
                        REFERENCES capabilities(capability_id, version)
                );

                CREATE INDEX IF NOT EXISTS idx_capability_events_latest
                ON capability_events(capability_id, version, event_id);

                CREATE TRIGGER IF NOT EXISTS capabilities_no_update
                BEFORE UPDATE ON capabilities
                BEGIN
                    SELECT RAISE(ABORT, 'capability records are immutable');
                END;

                CREATE TRIGGER IF NOT EXISTS capabilities_no_delete
                BEFORE DELETE ON capabilities
                BEGIN
                    SELECT RAISE(ABORT, 'capability records are immutable');
                END;

                CREATE TRIGGER IF NOT EXISTS capability_events_no_update
                BEFORE UPDATE ON capability_events
                BEGIN
                    SELECT RAISE(ABORT, 'capability events are append-only');
                END;

                CREATE TRIGGER IF NOT EXISTS capability_events_no_delete
                BEFORE DELETE ON capability_events
                BEGIN
                    SELECT RAISE(ABORT, 'capability events are append-only');
                END;
                """
            )

    @staticmethod
    def _required_text(name: str, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
        return value.strip()

    @classmethod
    def _validate_capability(cls, capability: Capability) -> None:
        for field_name in (
            "capability_id",
            "origin_project",
            "owner",
            "summary",
            "interface",
            "tests_ref",
            "changelog",
            "compatibility",
            "deprecation",
            "evidence_ref",
        ):
            cls._required_text(field_name, getattr(capability, field_name))
        if not _VERSION_RE.fullmatch(capability.version):
            raise ValueError("version must use MAJOR.MINOR.PATCH format")
        if capability.scope not in {"shared", "product_specific"}:
            raise ValueError("scope must be 'shared' or 'product_specific'")

    @staticmethod
    def _required_text_or_empty(name: str, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{name} must be a string")
        return value.strip()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _record(row: sqlite3.Row) -> dict[str, Any]:
        record = json.loads(row["record_json"])
        record["created_at"] = row["created_at"]
        return record

    def propose(self, capability: Capability, actor: str) -> None:
        """Register a new immutable capability version as proposed."""
        self._validate_capability(capability)
        actor = self._required_text("actor", actor)
        payload = {
            key: getattr(capability, key)
            for key in capability.__dataclass_fields__
        }
        now = self._now()
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO capabilities
                    (capability_id, version, record_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    capability.capability_id,
                    capability.version,
                    json.dumps(payload, sort_keys=True, separators=(",", ":")),
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO capability_events
                    (capability_id, version, status, actor, reason, occurred_at)
                VALUES (?, ?, 'proposed', ?, 'proposal submitted', ?)
                """,
                (capability.capability_id, capability.version, actor, now),
            )

    def promote(
        self,
        capability_id: str,
        version: str,
        review: CapabilityReview,
        actor: str,
    ) -> None:
        """Accept a proposal only after every explicit promotion gate passes."""
        actor = self._required_text("actor", actor)
        if not isinstance(review, CapabilityReview):
            raise TypeError("review must be a CapabilityReview")
        failed = [
            flag for flag in _REQUIRED_REVIEW_FLAGS
            if getattr(review, flag) is not True
        ]
        if failed:
            raise PromotionBlocked(
                "promotion review incomplete: " + ", ".join(failed)
            )
        external_use_case = self._required_text_or_empty(
            "external_project_use_case", review.external_project_use_case
        )
        factory_need = self._required_text_or_empty(
            "factory_need_reference", review.factory_need_reference
        )
        if not (external_use_case or factory_need):
            raise PromotionBlocked(
                "a second-project use case or documented factory need is required"
            )

        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT c.record_json,
                       (SELECT e.status FROM capability_events e
                        WHERE e.capability_id = c.capability_id
                          AND e.version = c.version
                        ORDER BY e.event_id DESC LIMIT 1) AS current_status
                FROM capabilities c
                WHERE c.capability_id = ? AND c.version = ?
                """,
                (capability_id, version),
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown capability version: {capability_id}@{version}")
            record = json.loads(row["record_json"])
            if row["current_status"] != "proposed":
                raise PromotionBlocked("only proposed capability versions can be promoted")
            if record["scope"] != "shared":
                raise PromotionBlocked("product-specific capabilities cannot enter TRADIX core")

            reason = json.dumps(
                {
                    "security_passed": review.security_passed,
                    "license_cleared": review.license_cleared,
                    "cost_assessed": review.cost_assessed,
                    "tests_passed": review.tests_passed,
                    "compatibility_passed": review.compatibility_passed,
                    "owner_approved": review.owner_approved,
                    "external_project_use_case": external_use_case,
                    "factory_need_reference": factory_need,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            connection.execute(
                """
                INSERT INTO capability_events
                    (capability_id, version, status, actor, reason, occurred_at)
                VALUES (?, ?, 'accepted', ?, ?, ?)
                """,
                (capability_id, version, actor, reason, self._now()),
            )

    def reject(self, capability_id: str, version: str, actor: str, reason: str) -> None:
        self._transition(capability_id, version, "rejected", actor, reason, {"proposed"})

    def deprecate(self, capability_id: str, version: str, actor: str, reason: str) -> None:
        self._transition(capability_id, version, "deprecated", actor, reason, {"accepted"})

    def _transition(
        self,
        capability_id: str,
        version: str,
        status: str,
        actor: str,
        reason: str,
        allowed_from: set[str],
    ) -> None:
        actor = self._required_text("actor", actor)
        reason = self._required_text("reason", reason)
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT status FROM capability_events
                WHERE capability_id = ? AND version = ?
                ORDER BY event_id DESC LIMIT 1
                """,
                (capability_id, version),
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown capability version: {capability_id}@{version}")
            if row["status"] not in allowed_from:
                raise PromotionBlocked(
                    f"cannot transition from {row['status']} to {status}"
                )
            connection.execute(
                """
                INSERT INTO capability_events
                    (capability_id, version, status, actor, reason, occurred_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (capability_id, version, status, actor, reason, self._now()),
            )

    def get(self, capability_id: str, version: str) -> dict[str, Any]:
        """Return one immutable record and its current event-derived status."""
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT c.record_json, c.created_at,
                       (SELECT e.status FROM capability_events e
                        WHERE e.capability_id = c.capability_id
                          AND e.version = c.version
                        ORDER BY e.event_id DESC LIMIT 1) AS status
                FROM capabilities c
                WHERE c.capability_id = ? AND c.version = ?
                """,
                (capability_id, version),
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown capability version: {capability_id}@{version}")
            result = self._record(row)
            result["status"] = row["status"]
            return result

    def list(self, status: str | None = None) -> list[dict[str, Any]]:
        """List latest status for each registered capability version."""
        if status is not None and status not in {
            "proposed", "accepted", "rejected", "deprecated"
        }:
            raise ValueError("unsupported status")
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT c.record_json, c.created_at,
                       (SELECT e.status FROM capability_events e
                        WHERE e.capability_id = c.capability_id
                          AND e.version = c.version
                        ORDER BY e.event_id DESC LIMIT 1) AS status
                FROM capabilities c
                ORDER BY c.capability_id, c.version
                """
            ).fetchall()
            records = []
            for row in rows:
                record = self._record(row)
                record["status"] = row["status"]
                if status is None or record["status"] == status:
                    records.append(record)
            return records

    def history(self, capability_id: str, version: str) -> list[dict[str, str]]:
        """Return the append-only lifecycle events for one capability version."""
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT status, actor, reason, occurred_at
                FROM capability_events
                WHERE capability_id = ? AND version = ?
                ORDER BY event_id
                """,
                (capability_id, version),
            ).fetchall()
            if not rows:
                raise KeyError(f"unknown capability version: {capability_id}@{version}")
            return [dict(row) for row in rows]
