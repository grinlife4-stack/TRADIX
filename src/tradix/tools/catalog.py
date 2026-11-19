"""Persistent, metadata-only catalog of versioned tools and lifecycle evidence."""
from __future__ import annotations
import json
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

_VERSION_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:[-+][0-9A-Za-z.-]+)?$")
_TOOL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_STATUSES = {"discovered", "evaluated", "approved", "connected", "suspended", "retired"}
_TRANSITIONS = {
    "discovered": {"evaluated", "suspended"},
    "evaluated": {"approved", "suspended", "retired"},
    "approved": {"connected", "suspended", "retired"},
    "connected": {"suspended", "retired"},
    "suspended": {"evaluated", "approved", "retired"},
    "retired": set(),
}


class ToolStatusError(ValueError):
    """Raised when a tool lifecycle transition is not permitted."""


@dataclass(frozen=True)
class ToolDescriptor:
    tool_id: str
    version: str
    category: str
    source_uri: str
    license_id: str
    platforms: tuple[str, ...]
    capabilities: tuple[str, ...]
    execution_modes: tuple[str, ...]
    adapter_contract_version: str
    free_open_source: bool
    notes: str = ""

    def validate(self) -> None:
        if not isinstance(self.tool_id, str) or not _TOOL_ID_RE.fullmatch(self.tool_id):
            raise ValueError("tool_id must be 1-64 lowercase letters, digits, dots, underscores, or hyphens")
        if not isinstance(self.version, str) or not _VERSION_RE.fullmatch(self.version):
            raise ValueError("version must use MAJOR.MINOR.PATCH format")
        for name in ("category", "license_id", "adapter_contract_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 128:
                raise ValueError(f"{name} must be a non-empty string of at most 128 characters")
        parsed = urlparse(self.source_uri) if isinstance(self.source_uri, str) else None
        if parsed is None or parsed.scheme != "https" or not parsed.hostname or parsed.username is not None or parsed.password is not None:
            raise ValueError("source_uri must be an absolute HTTPS URL without embedded credentials")
        for name in ("platforms", "capabilities", "execution_modes"):
            values = getattr(self, name)
            if not isinstance(values, tuple) or not values or len(values) > 64:
                raise ValueError(f"{name} must be a non-empty tuple of at most 64 values")
            if any(not isinstance(item, str) or not item.strip() or len(item) > 128 for item in values):
                raise ValueError(f"{name} entries must be non-empty strings of at most 128 characters")
            if len(set(values)) != len(values):
                raise ValueError(f"{name} entries must be unique")
        if type(self.free_open_source) is not bool:
            raise ValueError("free_open_source must be a boolean")
        if not isinstance(self.notes, str) or len(self.notes) > 4000:
            raise ValueError("notes must be a string of at most 4000 characters")


class ToolCatalog:
    """File-backed catalog of immutable descriptors and append-only lifecycle events."""

    def __init__(self, database: str | Path) -> None:
        self.database = str(database)
        if self.database == ":memory:":
            raise ValueError("ToolCatalog requires a file-backed SQLite database")
        Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA synchronous = FULL")
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
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS tools (
                    tool_id TEXT NOT NULL, version TEXT NOT NULL,
                    descriptor_json TEXT NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY (tool_id, version)
                );
                CREATE TABLE IF NOT EXISTS tool_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool_id TEXT NOT NULL, version TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN
                      ('discovered','evaluated','approved','connected','suspended','retired')),
                    actor TEXT NOT NULL, reason TEXT NOT NULL,
                    evidence_ref TEXT NOT NULL, occurred_at TEXT NOT NULL,
                    FOREIGN KEY (tool_id, version) REFERENCES tools(tool_id, version)
                );
                CREATE INDEX IF NOT EXISTS idx_tool_events_latest
                  ON tool_events(tool_id, version, event_id);
                CREATE TRIGGER IF NOT EXISTS tools_no_update BEFORE UPDATE ON tools
                  BEGIN SELECT RAISE(ABORT, 'tool descriptors are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS tools_no_delete BEFORE DELETE ON tools
                  BEGIN SELECT RAISE(ABORT, 'tool descriptors are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS tool_events_no_update BEFORE UPDATE ON tool_events
                  BEGIN SELECT RAISE(ABORT, 'tool events are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS tool_events_no_delete BEFORE DELETE ON tool_events
                  BEGIN SELECT RAISE(ABORT, 'tool events are append-only'); END;
            """)

    @staticmethod
    def _required(name: str, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
        value = value.strip()
        if len(value) > 512:
            raise ValueError(f"{name} must be at most 512 characters")
        return value

    @staticmethod
    def _validate_evidence_ref(value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ToolStatusError("this lifecycle transition requires an evidence reference")
        value = value.strip()
        parsed = urlparse(value)
        if parsed.scheme not in {"https", "evidence"} or not parsed.netloc:
            raise ToolStatusError("evidence_ref must be an absolute HTTPS or evidence:// reference")
        if parsed.username is not None or parsed.password is not None:
            raise ToolStatusError("evidence_ref must not contain embedded credentials")
        return value

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        record = json.loads(row["descriptor_json"])
        record["created_at"] = row["created_at"]
        for key in ("platforms", "capabilities", "execution_modes"):
            record[key] = tuple(record[key])
        return record

    def register(self, descriptor: ToolDescriptor, actor: str, reason: str = "tool discovered") -> None:
        if not isinstance(descriptor, ToolDescriptor):
            raise TypeError("descriptor must be a ToolDescriptor")
        descriptor.validate()
        actor, reason = self._required("actor", actor), self._required("reason", reason)
        now = self._now()
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO tools VALUES (?, ?, ?, ?)",
                (descriptor.tool_id, descriptor.version,
                 json.dumps(asdict(descriptor), sort_keys=True, separators=(",", ":")), now),
            )
            connection.execute(
                """INSERT INTO tool_events
                   (tool_id,version,status,actor,reason,evidence_ref,occurred_at)
                   VALUES (?,?,'discovered',?,?,'',?)""",
                (descriptor.tool_id, descriptor.version, actor, reason, now),
            )

    def get(self, tool_id: str, version: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                """SELECT t.descriptor_json,t.created_at,
                   (SELECT e.status FROM tool_events e WHERE e.tool_id=t.tool_id
                    AND e.version=t.version ORDER BY e.event_id DESC LIMIT 1) AS status
                   FROM tools t WHERE t.tool_id=? AND t.version=?""",
                (tool_id, version),
            ).fetchone()
        if row is None:
            return None
        record = self._decode(row)
        record["status"] = row["status"]
        return record

    def list_tools(self, status: str | None = None, category: str | None = None) -> list[dict[str, Any]]:
        if status is not None and status not in _STATUSES:
            raise ValueError("unknown tool status")
        query = """SELECT t.descriptor_json,t.created_at,
          (SELECT e.status FROM tool_events e WHERE e.tool_id=t.tool_id AND e.version=t.version
           ORDER BY e.event_id DESC LIMIT 1) AS status FROM tools t"""
        clauses, params = [], []
        if status is not None:
            clauses.append("""(SELECT e.status FROM tool_events e WHERE e.tool_id=t.tool_id
              AND e.version=t.version ORDER BY e.event_id DESC LIMIT 1)=?""")
            params.append(status)
        if category is not None:
            clauses.append("json_extract(t.descriptor_json,'$.category')=?")
            params.append(self._required("category", category))
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY json_extract(t.descriptor_json,'$.tool_id'), json_extract(t.descriptor_json,'$.version')"
        with self._connection() as connection:
            rows = connection.execute(query, params).fetchall()
        result = []
        for row in rows:
            item = self._decode(row)
            item["status"] = row["status"]
            result.append(item)
        return result

    def transition(self, tool_id: str, version: str, status: str, actor: str,
                   reason: str, evidence_ref: str = "") -> None:
        if status not in _STATUSES:
            raise ToolStatusError("unknown tool status")
        actor, reason = self._required("actor", actor), self._required("reason", reason)
        if not isinstance(evidence_ref, str):
            raise ValueError("evidence_ref must be a string")
        evidence_ref = evidence_ref.strip()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT e.status FROM tools t JOIN tool_events e
                   ON e.tool_id=t.tool_id AND e.version=t.version
                   WHERE t.tool_id=? AND t.version=? AND e.event_id=(
                     SELECT MAX(e2.event_id) FROM tool_events e2
                     WHERE e2.tool_id=t.tool_id AND e2.version=t.version)""",
                (tool_id, version),
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown tool version: {tool_id}@{version}")
            current = row["status"]
            if status not in _TRANSITIONS[current]:
                raise ToolStatusError(f"transition {current} -> {status} is not allowed")
            if status in {"evaluated", "approved", "connected"}:
                evidence_ref = self._validate_evidence_ref(evidence_ref)
            connection.execute(
                """INSERT INTO tool_events
                   (tool_id,version,status,actor,reason,evidence_ref,occurred_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (tool_id, version, status, actor, reason, evidence_ref, self._now()),
            )

    def history(self, tool_id: str, version: str) -> list[dict[str, str]]:
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT status,actor,reason,evidence_ref,occurred_at FROM tool_events
                   WHERE tool_id=? AND version=? ORDER BY event_id""",
                (tool_id, version),
            ).fetchall()
        return [dict(row) for row in rows]
