from __future__ import annotations
import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Iterable, Mapping

class StoreError(ValueError):
    pass

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")

class ProjectStore:
    """One append-only SQLite store per project."""
    def __init__(self, root: str | Path, project_id: str) -> None:
        if not isinstance(project_id, str) or not _ID.fullmatch(project_id):
            raise StoreError("invalid project_id")
        self.root = Path(root).expanduser().resolve()
        self.project_id = project_id
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / f"{project_id}.sqlite3"
        self._initialize()

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def _initialize(self) -> None:
        with closing(self._connect()) as db:
            with db:
                db.executescript("""
                CREATE TABLE IF NOT EXISTS coverage (
                  scan_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, source_id TEXT NOT NULL,
                  requested_scope TEXT NOT NULL, coverage_state TEXT NOT NULL,
                  started_at TEXT NOT NULL, finished_at TEXT NOT NULL, actor_id TEXT NOT NULL,
                  adapter_id TEXT NOT NULL, adapter_version TEXT NOT NULL,
                  items_seen INTEGER NOT NULL CHECK(items_seen >= 0), pages_seen INTEGER NOT NULL CHECK(pages_seen >= 0),
                  reason_code TEXT, limitations_json TEXT NOT NULL, checkpoint_ref TEXT
                );
                CREATE TABLE IF NOT EXISTS measurements (
                  measurement_id TEXT PRIMARY KEY, scan_id TEXT NOT NULL REFERENCES coverage(scan_id),
                  project_id TEXT NOT NULL, source_id TEXT NOT NULL, kind TEXT NOT NULL,
                  value REAL NOT NULL CHECK(value >= 0), unit TEXT NOT NULL, measured_at TEXT NOT NULL,
                  source_timestamp TEXT, method TEXT NOT NULL, adapter_id TEXT NOT NULL, adapter_version TEXT NOT NULL,
                  coverage_state TEXT NOT NULL, confidence TEXT NOT NULL, limitations_json TEXT NOT NULL,
                  evidence_ref TEXT, checkpoint_ref TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_measurements_project_source_time ON measurements(project_id, source_id, measured_at);
                CREATE TABLE IF NOT EXISTS checkpoints (
                  source_id TEXT NOT NULL, scan_id TEXT NOT NULL, checkpoint_json TEXT NOT NULL,
                  updated_at TEXT NOT NULL, PRIMARY KEY(source_id, scan_id)
                );
                """)

    @staticmethod
    def _coverage_values(record: Mapping[str, Any]):
        return (record["scan_id"], record["project_id"], record["source_id"], record["requested_scope"], record["coverage_state"], record["started_at"], record["finished_at"], record["actor_id"], record["adapter_id"], record["adapter_version"], record["items_seen"], record["pages_seen"], record["reason_code"], json.dumps(record["limitations"], ensure_ascii=False), record["checkpoint_ref"])

    @staticmethod
    def _measurement_values(record: Mapping[str, Any]):
        return (record["measurement_id"], record["scan_id"], record["project_id"], record["source_id"], record["kind"], record["value"], record["unit"], record["measured_at"], record["source_timestamp"], record["method"], record["adapter_id"], record["adapter_version"], record["coverage_state"], record["confidence"], json.dumps(record["limitations"], ensure_ascii=False), record["evidence_ref"], record["checkpoint_ref"])

    def append_scan(self, coverage: Mapping[str, Any], measurements: Iterable[Mapping[str, Any]], checkpoint: Mapping[str, Any] | None = None, checkpoint_updated_at: str | None = None) -> None:
        if coverage.get("project_id") != self.project_id:
            raise StoreError("coverage project_id does not match project store")
        items = list(measurements)
        for item in items:
            if item.get("project_id") != self.project_id or item.get("source_id") != coverage.get("source_id") or item.get("scan_id", coverage.get("scan_id")) != coverage.get("scan_id"):
                raise StoreError("measurement project_id and source_id must match coverage and project store")
        if checkpoint is not None and (not isinstance(checkpoint, Mapping) or not isinstance(checkpoint_updated_at, str)):
            raise StoreError("checkpoint and checkpoint_updated_at must be provided together")
        with closing(self._connect()) as db:
            with db:
                db.execute("INSERT INTO coverage VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", self._coverage_values(coverage))
                for item in items:
                    db.execute("INSERT INTO measurements VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", self._measurement_values({**item, "scan_id": coverage["scan_id"]}))
                if checkpoint is not None:
                    db.execute("INSERT INTO checkpoints VALUES (?,?,?,?)", (coverage["source_id"], coverage["scan_id"], json.dumps(dict(checkpoint), ensure_ascii=False), checkpoint_updated_at))

    def list_coverage(self, source_id: str | None = None) -> list[dict[str, Any]]:
        with closing(self._connect()) as db:
            rows = db.execute("SELECT * FROM coverage WHERE (? IS NULL OR source_id=?) ORDER BY started_at,scan_id", (source_id, source_id)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["limitations"] = json.loads(item.pop("limitations_json"))
            result.append(item)
        return result

    def list_measurements(self, source_id: str | None = None) -> list[dict[str, Any]]:
        with closing(self._connect()) as db:
            rows = db.execute("SELECT * FROM measurements WHERE (? IS NULL OR source_id=?) ORDER BY measured_at,measurement_id", (source_id, source_id)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["limitations"] = json.loads(item.pop("limitations_json"))
            result.append(item)
        return result

    def save_checkpoint(self, source_id: str, scan_id: str, checkpoint: Mapping[str, Any], updated_at: str) -> None:
        if not _ID.fullmatch(source_id) or not scan_id or not isinstance(checkpoint, Mapping):
            raise StoreError("invalid checkpoint")
        with closing(self._connect()) as db:
            with db:
                db.execute("INSERT INTO checkpoints VALUES (?,?,?,?) ON CONFLICT(source_id,scan_id) DO UPDATE SET checkpoint_json=excluded.checkpoint_json, updated_at=excluded.updated_at", (source_id, scan_id, json.dumps(dict(checkpoint), ensure_ascii=False), updated_at))

    def load_checkpoint(self, source_id: str, scan_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as db:
            row = db.execute("SELECT checkpoint_json FROM checkpoints WHERE source_id=? AND scan_id=?", (source_id, scan_id)).fetchone()
        return json.loads(row[0]) if row else None

    def export_bundle(self) -> dict[str, Any]:
        with closing(self._connect()) as db:
            coverage = [dict(r) for r in db.execute("SELECT * FROM coverage ORDER BY started_at,scan_id").fetchall()]
            measurements = [dict(r) for r in db.execute("SELECT * FROM measurements ORDER BY measured_at,measurement_id").fetchall()]
            checkpoints = [dict(r) for r in db.execute("SELECT * FROM checkpoints ORDER BY updated_at,source_id,scan_id").fetchall()]
        for row in coverage:
            row["limitations"] = json.loads(row.pop("limitations_json"))
        for row in measurements:
            row["limitations"] = json.loads(row.pop("limitations_json"))
        for row in checkpoints:
            row["checkpoint"] = json.loads(row.pop("checkpoint_json"))
        return {"coverage": coverage, "measurements": measurements, "checkpoints": checkpoints}

    def import_bundle(self, bundle: Mapping[str, Any]) -> int:
        coverage = bundle.get("coverage", [])
        measurements = bundle.get("measurements", [])
        checkpoints = bundle.get("checkpoints", [])
        if not all(isinstance(x, list) for x in (coverage, measurements, checkpoints)):
            raise StoreError("bundle record collections must be arrays")
        coverage_by_scan = {}
        for record in coverage:
            if not isinstance(record, dict) or record.get("project_id") != self.project_id:
                raise StoreError("coverage project does not match destination store")
            scan_id, source_id = record.get("scan_id"), record.get("source_id")
            if not isinstance(scan_id, str) or not scan_id or not isinstance(source_id, str) or not source_id:
                raise StoreError("coverage record has invalid identifiers")
            if scan_id in coverage_by_scan:
                raise StoreError("duplicate scan_id in import bundle")
            coverage_by_scan[scan_id] = source_id
        for record in measurements:
            if not isinstance(record, dict) or record.get("project_id") != self.project_id:
                raise StoreError("measurement project does not match destination store")
            if coverage_by_scan.get(record.get("scan_id")) != record.get("source_id"):
                raise StoreError("measurement source and scan must match the imported coverage record")
        for record in checkpoints:
            if not isinstance(record, dict) or not isinstance(record.get("checkpoint"), dict):
                raise StoreError("invalid checkpoint export")
            if coverage_by_scan.get(record.get("scan_id")) != record.get("source_id"):
                raise StoreError("checkpoint source and scan must match the imported coverage record")

        inserted = 0
        with closing(self._connect()) as db:
            with db:
                for record in coverage:
                    existing = db.execute("SELECT * FROM coverage WHERE scan_id=?", (record["scan_id"],)).fetchone()
                    if existing:
                        current = dict(existing)
                        current["limitations"] = json.loads(current.pop("limitations_json"))
                        if current != record:
                            raise StoreError("conflicting duplicate scan_id in destination store")
                        continue
                    db.execute("INSERT INTO coverage VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", self._coverage_values({**record, "limitations": record.get("limitations", [])}))
                    inserted += 1
                for record in measurements:
                    existing = db.execute("SELECT * FROM measurements WHERE measurement_id=?", (record["measurement_id"],)).fetchone()
                    if existing:
                        current = dict(existing)
                        current["limitations"] = json.loads(current.pop("limitations_json"))
                        if current != {**record, "limitations": record.get("limitations", [])}:
                            raise StoreError("conflicting duplicate measurement_id in destination store")
                        continue
                    db.execute("INSERT INTO measurements VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", self._measurement_values({**record, "limitations": record.get("limitations", [])}))
                    inserted += 1
                for record in checkpoints:
                    existing = db.execute("SELECT * FROM checkpoints WHERE source_id=? AND scan_id=?", (record["source_id"], record["scan_id"])).fetchone()
                    if existing:
                        current = dict(existing)
                        current["checkpoint"] = json.loads(current.pop("checkpoint_json"))
                        if current != record:
                            raise StoreError("conflicting duplicate checkpoint in destination store")
                        continue
                    db.execute("INSERT INTO checkpoints VALUES (?,?,?,?)", (record["source_id"], record["scan_id"], json.dumps(record["checkpoint"], ensure_ascii=False), record["updated_at"]))
                    inserted += 1
        return inserted
