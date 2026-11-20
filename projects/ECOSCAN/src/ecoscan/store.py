"""Per-project SQLite persistence with append-only measurement and coverage rows."""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

IDENTIFIER = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")
STORE_SCHEMA_VERSION = "0.1"


class StoreError(ValueError):
    """Raised when a project store operation violates its isolation contract."""


class ProjectStore:
    def __init__(self, data_root: str | Path, project_id: str) -> None:
        if not isinstance(project_id, str) or not IDENTIFIER.fullmatch(project_id):
            raise StoreError("invalid project_id")
        self.project_id = project_id
        self.project_dir = Path(data_root).expanduser().resolve() / "projects" / project_id
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.project_dir / "state.sqlite3"
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5.0)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS store_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS measurements (
                    measurement_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_measurements_source
                    ON measurements(source_id, observed_at);
                CREATE TABLE IF NOT EXISTS coverage (
                    scan_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_coverage_source
                    ON coverage(source_id, started_at);
                CREATE TABLE IF NOT EXISTS checkpoints (
                    source_id TEXT NOT NULL,
                    scan_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(source_id, scan_id)
                );
                """
            )
            row = connection.execute(
                "SELECT value FROM store_meta WHERE key = 'schema_version'"
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO store_meta(key, value) VALUES('schema_version', ?)",
                    (STORE_SCHEMA_VERSION,),
                )
            elif row[0] != STORE_SCHEMA_VERSION:
                raise StoreError("unsupported project store schema version")

    @staticmethod
    def _payload(value: Mapping[str, Any]) -> str:
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError, OverflowError) as exc:
            raise StoreError("record is not valid finite JSON data") from exc

    def append_scan(
        self,
        coverage_record: Mapping[str, Any],
        measurements: list[Mapping[str, Any]],
        checkpoint: Mapping[str, Any] | None = None,
        checkpoint_updated_at: str | None = None,
    ) -> None:
        if coverage_record.get("project_id") != self.project_id:
            raise StoreError("coverage project_id does not match this project store")
        source_id = coverage_record.get("source_id")
        scan_id = coverage_record.get("scan_id")
        started_at = coverage_record.get("started_at")
        if not isinstance(source_id, str) or not source_id or not isinstance(scan_id, str) or not scan_id:
            raise StoreError("coverage must contain source_id and scan_id")
        if not isinstance(started_at, str) or not started_at:
            raise StoreError("coverage must contain started_at")

        prepared: list[tuple[str, str, str, str, str]] = []
        for record in measurements:
            if record.get("project_id") != self.project_id or record.get("source_id") != source_id:
                raise StoreError("measurement project/source must match the coverage record")
            measurement_id = record.get("measurement_id")
            observed_at = record.get("measured_at")
            if not isinstance(measurement_id, str) or not measurement_id:
                raise StoreError("measurement_id is required")
            if not isinstance(observed_at, str) or not observed_at:
                raise StoreError("measured_at is required")
            prepared.append((
                measurement_id, self.project_id, source_id, observed_at, self._payload(record)
            ))

        coverage_json = self._payload(coverage_record)
        checkpoint_json = None
        if checkpoint is not None:
            if not isinstance(checkpoint_updated_at, str) or not checkpoint_updated_at:
                raise StoreError("checkpoint_updated_at is required when a checkpoint is supplied")
            checkpoint_json = self._payload(checkpoint)
        elif checkpoint_updated_at is not None:
            raise StoreError("checkpoint_updated_at cannot be supplied without a checkpoint")
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO coverage(scan_id, project_id, source_id, started_at, payload_json) VALUES(?, ?, ?, ?, ?)",
                (scan_id, self.project_id, source_id, started_at, coverage_json),
            )
            connection.executemany(
                "INSERT INTO measurements(measurement_id, project_id, source_id, observed_at, payload_json) VALUES(?, ?, ?, ?, ?)",
                prepared,
            )
            if checkpoint_json is not None:
                connection.execute(
                    """INSERT INTO checkpoints(source_id, scan_id, payload_json, updated_at)
                       VALUES(?, ?, ?, ?)
                       ON CONFLICT(source_id, scan_id) DO UPDATE SET
                         payload_json = excluded.payload_json,
                         updated_at = excluded.updated_at""",
                    (source_id, scan_id, checkpoint_json, checkpoint_updated_at),
                )

    def save_checkpoint(
        self, source_id: str, scan_id: str, payload: Mapping[str, Any], updated_at: str
    ) -> None:
        if not source_id or not scan_id or not updated_at:
            raise StoreError("checkpoint identity and timestamp are required")
        encoded = self._payload(payload)
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO checkpoints(source_id, scan_id, payload_json, updated_at)
                   VALUES(?, ?, ?, ?)
                   ON CONFLICT(source_id, scan_id) DO UPDATE SET
                     payload_json = excluded.payload_json,
                     updated_at = excluded.updated_at""",
                (source_id, scan_id, encoded, updated_at),
            )

    def load_checkpoint(self, source_id: str, scan_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM checkpoints WHERE source_id = ? AND scan_id = ?",
                (source_id, scan_id),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def list_measurements(self, source_id: str | None = None) -> list[dict[str, Any]]:
        with self._connect() as connection:
            if source_id is None:
                rows = connection.execute(
                    "SELECT payload_json FROM measurements ORDER BY observed_at, measurement_id"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT payload_json FROM measurements WHERE source_id = ? ORDER BY observed_at, measurement_id",
                    (source_id,),
                ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def list_coverage(self, source_id: str | None = None) -> list[dict[str, Any]]:
        with self._connect() as connection:
            if source_id is None:
                rows = connection.execute(
                    "SELECT payload_json FROM coverage ORDER BY started_at, scan_id"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT payload_json FROM coverage WHERE source_id = ? ORDER BY started_at, scan_id",
                    (source_id,),
                ).fetchall()
        return [json.loads(row[0]) for row in rows]
