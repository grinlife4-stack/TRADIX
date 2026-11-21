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
                  scan_id TEXT PRIMARY KEY, schema_version TEXT NOT NULL DEFAULT '0.1', project_id TEXT NOT NULL, source_id TEXT NOT NULL,
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
                CREATE TABLE IF NOT EXISTS operation_intents (
                  scan_id TEXT PRIMARY KEY,
                  operation_id TEXT NOT NULL UNIQUE,
                  idempotency_key TEXT NOT NULL UNIQUE,
                  project_id TEXT NOT NULL,
                  source_id TEXT NOT NULL,
                  peer_id TEXT NOT NULL,
                  principal_ref TEXT NOT NULL,
                  capability_id TEXT NOT NULL,
                  capability_version TEXT NOT NULL,
                  resource_json TEXT NOT NULL,
                  payload_sha256 TEXT NOT NULL,
                  request_hash TEXT NOT NULL DEFAULT '',
                  state TEXT NOT NULL CHECK(state IN ('PREPARED','INDETERMINATE','RECONCILED_SUCCEEDED','RECONCILED_FAILED')),
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_operation_intents_unresolved
                  ON operation_intents(state, created_at);
                CREATE TABLE IF NOT EXISTS operation_reconciliations (
                  reconciliation_id TEXT PRIMARY KEY,
                  scan_id TEXT NOT NULL REFERENCES operation_intents(scan_id),
                  project_id TEXT NOT NULL,
                  source_id TEXT NOT NULL,
                  outcome TEXT NOT NULL CHECK(outcome IN ('SUCCEEDED','FAILED')),
                  recorded_at TEXT NOT NULL,
                  result_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_operation_reconciliations_scan
                  ON operation_reconciliations(scan_id, recorded_at);
                CREATE TABLE IF NOT EXISTS reconciliation_measurement_links (
                  reconciliation_id TEXT NOT NULL REFERENCES operation_reconciliations(reconciliation_id),
                  measurement_id TEXT NOT NULL UNIQUE REFERENCES measurements(measurement_id),
                  scan_id TEXT NOT NULL REFERENCES coverage(scan_id),
                  source_id TEXT NOT NULL,
                  kind TEXT NOT NULL,
                  PRIMARY KEY(reconciliation_id, kind)
                );
                CREATE INDEX IF NOT EXISTS idx_reconciliation_measurement_links_scan
                  ON reconciliation_measurement_links(scan_id, reconciliation_id);
                """)
            columns = {row[1] for row in db.execute("PRAGMA table_info(coverage)")}
            if "schema_version" not in columns:
                db.execute("ALTER TABLE coverage ADD COLUMN schema_version TEXT NOT NULL DEFAULT '0.1'")
            intent_columns = {row[1] for row in db.execute("PRAGMA table_info(operation_intents)")}
            if "request_hash" not in intent_columns:
                db.execute("ALTER TABLE operation_intents ADD COLUMN request_hash TEXT NOT NULL DEFAULT ''")

    @staticmethod
    def _coverage_values(record: Mapping[str, Any]):
        return (record["scan_id"], record.get("schema_version", "0.1"), record["project_id"], record["source_id"], record["requested_scope"], record["coverage_state"], record["started_at"], record["finished_at"], record["actor_id"], record["adapter_id"], record["adapter_version"], record["items_seen"], record["pages_seen"], record["reason_code"], json.dumps(record["limitations"], ensure_ascii=False), record["checkpoint_ref"])

    @staticmethod
    def _measurement_values(record: Mapping[str, Any]):
        return (record["measurement_id"], record["scan_id"], record["project_id"], record["source_id"], record["kind"], record["value"], record["unit"], record["measured_at"], record["source_timestamp"], record["method"], record["adapter_id"], record["adapter_version"], record["coverage_state"], record["confidence"], json.dumps(record["limitations"], ensure_ascii=False), record["evidence_ref"], record["checkpoint_ref"])

    def append_scan(self, coverage: Mapping[str, Any], measurements: Iterable[Mapping[str, Any]], checkpoint: Mapping[str, Any] | None = None, checkpoint_updated_at: str | None = None, reconcile_operation_intent: bool = False) -> None:
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
                db.execute("INSERT INTO coverage (scan_id,schema_version,project_id,source_id,requested_scope,coverage_state,started_at,finished_at,actor_id,adapter_id,adapter_version,items_seen,pages_seen,reason_code,limitations_json,checkpoint_ref) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", self._coverage_values(coverage))
                for item in items:
                    db.execute("INSERT INTO measurements VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", self._measurement_values({**item, "scan_id": coverage["scan_id"]}))
                if checkpoint is not None:
                    db.execute("INSERT INTO checkpoints VALUES (?,?,?,?)", (coverage["source_id"], coverage["scan_id"], json.dumps(dict(checkpoint), ensure_ascii=False), checkpoint_updated_at))
                if reconcile_operation_intent:
                    cursor = db.execute(
                        """UPDATE operation_intents
                           SET state='RECONCILED_SUCCEEDED', updated_at=?
                           WHERE scan_id=? AND state IN ('PREPARED','INDETERMINATE')""",
                        (coverage["finished_at"], coverage["scan_id"]),
                    )
                    if cursor.rowcount != 1:
                        raise StoreError("operation intent could not be atomically reconciled with scan commit")

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

    def create_operation_intent(
        self, *, scan_id: str, operation_id: str, idempotency_key: str,
        source_id: str, peer_id: str, principal_ref: str,
        capability_id: str, capability_version: str,
        resource: Mapping[str, str], payload_sha256: str, request_hash: str, created_at: str,
    ) -> dict[str, Any]:
        identifiers = {
            "scan_id": scan_id, "operation_id": operation_id,
            "idempotency_key": idempotency_key, "source_id": source_id,
            "peer_id": peer_id, "principal_ref": principal_ref,
            "capability_id": capability_id, "capability_version": capability_version,
        }
        if any(not isinstance(v, str) or not _ID.fullmatch(v) for v in identifiers.values()):
            raise StoreError("operation intent contains an invalid identifier")
        if not isinstance(resource, Mapping) or set(resource) != {"project_id", "source_id"}:
            raise StoreError("operation intent resource must bind project_id and source_id")
        if resource.get("project_id") != self.project_id or resource.get("source_id") != source_id:
            raise StoreError("operation intent resource crosses project/source boundary")
        if not isinstance(payload_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", payload_sha256):
            raise StoreError("operation intent payload_sha256 must be lowercase SHA-256")
        if not isinstance(request_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", request_hash):
            raise StoreError("operation intent request_hash must be lowercase SHA-256")
        if not isinstance(created_at, str) or not created_at:
            raise StoreError("operation intent created_at is required")
        resource_json = json.dumps(dict(resource), sort_keys=True, separators=(",", ":"))
        with closing(self._connect()) as db:
            with db:
                db.execute(
                    """INSERT INTO operation_intents
                    (scan_id,operation_id,idempotency_key,project_id,source_id,peer_id,
                     principal_ref,capability_id,capability_version,resource_json,
                     payload_sha256,request_hash,state,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'PREPARED',?,?)""",
                    (scan_id,operation_id,idempotency_key,self.project_id,source_id,peer_id,
                     principal_ref,capability_id,capability_version,resource_json,
                     payload_sha256,request_hash,created_at,created_at),
                )
        return self.get_operation_intent(scan_id)

    def get_operation_intent(self, scan_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM operation_intents WHERE scan_id=?", (scan_id,)).fetchone()
        if row is None:
            return None
        item = dict(row)
        item["resource"] = json.loads(item.pop("resource_json"))
        return item

    def list_unresolved_operation_intents(self, source_id: str | None = None) -> list[dict[str, Any]]:
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT * FROM operation_intents
                   WHERE state IN ('PREPARED','INDETERMINATE')
                     AND (? IS NULL OR source_id=?)
                   ORDER BY created_at,scan_id""",
                (source_id, source_id),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["resource"] = json.loads(item.pop("resource_json"))
            result.append(item)
        return result

    def transition_operation_intent(self, scan_id: str, state: str, updated_at: str) -> dict[str, Any]:
        allowed = {
            "PREPARED": {"INDETERMINATE", "RECONCILED_SUCCEEDED", "RECONCILED_FAILED"},
            "INDETERMINATE": {"RECONCILED_SUCCEEDED", "RECONCILED_FAILED"},
            "RECONCILED_SUCCEEDED": set(),
            "RECONCILED_FAILED": set(),
        }
        if state not in allowed or not isinstance(updated_at, str) or not updated_at:
            raise StoreError("invalid operation intent transition")
        with closing(self._connect()) as db:
            with db:
                row = db.execute("SELECT state FROM operation_intents WHERE scan_id=?", (scan_id,)).fetchone()
                if row is None:
                    raise StoreError("operation intent does not exist")
                current = row["state"]
                if state not in allowed[current]:
                    raise StoreError(f"illegal operation intent transition: {current} -> {state}")
                db.execute(
                    "UPDATE operation_intents SET state=?,updated_at=? WHERE scan_id=?",
                    (state, updated_at, scan_id),
                )
        result = self.get_operation_intent(scan_id)
        if result is None:
            raise StoreError("operation intent disappeared after transition")
        return result

    def append_operation_reconciliation(
        self, *, reconciliation_id: str, scan_id: str, source_id: str,
        outcome: str, recorded_at: str, result: Mapping[str, Any],
    ) -> None:
        if not all(isinstance(v, str) and _ID.fullmatch(v) for v in
                   (reconciliation_id, scan_id, source_id)):
            raise StoreError("invalid reconciliation identifiers")
        if outcome not in {"SUCCEEDED", "FAILED"} or not isinstance(recorded_at, str) or not recorded_at:
            raise StoreError("invalid reconciliation outcome or timestamp")
        if not isinstance(result, Mapping):
            raise StoreError("reconciliation result must be an object")
        encoded = json.dumps(dict(result), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        target_state = "RECONCILED_SUCCEEDED" if outcome == "SUCCEEDED" else "RECONCILED_FAILED"
        with closing(self._connect()) as db:
            with db:
                intent = db.execute(
                    "SELECT project_id,source_id,state FROM operation_intents WHERE scan_id=?",
                    (scan_id,),
                ).fetchone()
                if intent is None or intent["project_id"] != self.project_id or intent["source_id"] != source_id:
                    raise StoreError("reconciliation does not match a durable operation intent")
                if intent["state"] not in {"PREPARED", "INDETERMINATE"}:
                    raise StoreError("operation intent is already terminal")
                db.execute(
                    """INSERT INTO operation_reconciliations
                       (reconciliation_id,scan_id,project_id,source_id,outcome,recorded_at,result_json)
                       VALUES (?,?,?,?,?,?,?)""",
                    (reconciliation_id,scan_id,self.project_id,source_id,outcome,recorded_at,encoded),
                )
                cursor = db.execute(
                    """UPDATE operation_intents SET state=?,updated_at=?
                       WHERE scan_id=? AND state IN ('PREPARED','INDETERMINATE')""",
                    (target_state,recorded_at,scan_id),
                )
                if cursor.rowcount != 1:
                    raise StoreError("intent state changed during reconciliation commit")

    def list_operation_reconciliations(self, source_id: str | None = None) -> list[dict[str, Any]]:
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT * FROM operation_reconciliations
                   WHERE (? IS NULL OR source_id=?) ORDER BY recorded_at,reconciliation_id""",
                (source_id,source_id),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["result"] = json.loads(item.pop("result_json"))
            result.append(item)
        return result

    def list_reconciliation_measurement_links(self, source_id: str | None = None) -> list[dict[str, Any]]:
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT * FROM reconciliation_measurement_links
                   WHERE (? IS NULL OR source_id=?)
                   ORDER BY reconciliation_id,kind""",
                (source_id, source_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def append_reconciliation_measurements(
        self, *, reconciliation_id: str, measurements: Iterable[Mapping[str, Any]],
    ) -> int:
        items = list(measurements)
        if not items:
            raise StoreError("reconciliation projection must contain measurements")
        kinds = [item.get("kind") for item in items]
        if any(not isinstance(kind, str) or not kind for kind in kinds) or len(set(kinds)) != len(kinds):
            raise StoreError("reconciliation projection kinds must be unique")
        with closing(self._connect()) as db:
            with db:
                event = db.execute(
                    """SELECT scan_id,project_id,source_id,outcome,result_json
                       FROM operation_reconciliations WHERE reconciliation_id=?""",
                    (reconciliation_id,),
                ).fetchone()
                if event is None or event["project_id"] != self.project_id or event["outcome"] != "SUCCEEDED":
                    raise StoreError("projection requires a successful reconciliation event")
                coverage = db.execute(
                    "SELECT coverage_state,source_id FROM coverage WHERE scan_id=?",
                    (event["scan_id"],),
                ).fetchone()
                if coverage is None or coverage["coverage_state"] != "INDETERMINATE" or coverage["source_id"] != event["source_id"]:
                    raise StoreError("projection must reference the original INDETERMINATE coverage")
                recovered_result = json.loads(event["result_json"])
                recovered_values = recovered_result.get("measurements")
                if not isinstance(recovered_values, dict):
                    raise StoreError("successful reconciliation has no measurement map")
                inserted = 0
                for item in items:
                    if (item.get("project_id") != self.project_id
                            or item.get("source_id") != event["source_id"]
                            or item.get("scan_id") != event["scan_id"]
                            or item.get("coverage_state") not in {"COMPLETE", "PARTIAL"}
                            or item.get("coverage_state") != recovered_result.get("coverage_state")
                            or recovered_values.get(item.get("kind")) != item.get("value")
                            or item.get("measured_at") != event["recorded_at"]
                            or item.get("source_timestamp") != recovered_result.get("source_timestamp")
                            or item.get("evidence_ref") != recovered_result.get("evidence_ref")
                            or item.get("confidence") != "UNVERIFIED"
                            or item.get("method") != f"obis_v0.2_status_reconciliation:{reconciliation_id}"):
                        raise StoreError("projected measurement does not faithfully represent its reconciliation event")
                    existing = db.execute(
                        """SELECT l.*,m.* FROM reconciliation_measurement_links l
                           JOIN measurements m ON m.measurement_id=l.measurement_id
                           WHERE l.reconciliation_id=? AND l.kind=?""",
                        (reconciliation_id, item["kind"]),
                    ).fetchone()
                    if existing:
                        current = dict(existing)
                        current["limitations"] = json.loads(current.pop("limitations_json"))
                        expected = {**item, "limitations": list(item.get("limitations", []))}
                        if current["measurement_id"] != item["measurement_id"] or any(
                            current.get(key) != value for key, value in expected.items()
                        ):
                            raise StoreError("conflicting duplicate reconciliation measurement projection")
                        continue
                    db.execute(
                        "INSERT INTO measurements VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        self._measurement_values(item),
                    )
                    db.execute(
                        """INSERT INTO reconciliation_measurement_links
                           (reconciliation_id,measurement_id,scan_id,source_id,kind)
                           VALUES (?,?,?,?,?)""",
                        (reconciliation_id,item["measurement_id"],event["scan_id"],event["source_id"],item["kind"]),
                    )
                    inserted += 1
        return inserted

    def export_bundle(self) -> dict[str, Any]:
        with closing(self._connect()) as db:
            coverage = [dict(r) for r in db.execute("SELECT * FROM coverage ORDER BY started_at,scan_id").fetchall()]
            measurements = [dict(r) for r in db.execute("SELECT * FROM measurements ORDER BY measured_at,measurement_id").fetchall()]
            checkpoints = [dict(r) for r in db.execute("SELECT * FROM checkpoints ORDER BY updated_at,source_id,scan_id").fetchall()]
            reconciliations = [dict(r) for r in db.execute(
                "SELECT * FROM operation_reconciliations ORDER BY recorded_at,reconciliation_id"
            ).fetchall()]
            intents = [dict(r) for r in db.execute(
                "SELECT * FROM operation_intents ORDER BY created_at,scan_id"
            ).fetchall()]
            reconciliation_measurement_links = [dict(r) for r in db.execute(
                "SELECT * FROM reconciliation_measurement_links ORDER BY reconciliation_id,kind"
            ).fetchall()]
        for row in coverage:
            row["limitations"] = json.loads(row.pop("limitations_json"))
        for row in measurements:
            row["limitations"] = json.loads(row.pop("limitations_json"))
        for row in checkpoints:
            row["checkpoint"] = json.loads(row.pop("checkpoint_json"))
        for row in reconciliations:
            row["result"] = json.loads(row.pop("result_json"))
        for row in intents:
            row["resource"] = json.loads(row.pop("resource_json"))
        return {"coverage": coverage, "measurements": measurements, "checkpoints": checkpoints,
                "operation_intents": intents, "operation_reconciliations": reconciliations,
                "reconciliation_measurement_links": reconciliation_measurement_links}

    def import_bundle(self, bundle: Mapping[str, Any]) -> int:
        coverage = bundle.get("coverage", [])
        measurements = bundle.get("measurements", [])
        checkpoints = bundle.get("checkpoints", [])
        intents = bundle.get("operation_intents", [])
        reconciliations = bundle.get("operation_reconciliations", [])
        reconciliation_measurement_links = bundle.get("reconciliation_measurement_links", [])
        if not all(isinstance(x, list) for x in (coverage, measurements, checkpoints, intents, reconciliations, reconciliation_measurement_links)):
            raise StoreError("bundle record collections must be arrays")
        intent_by_scan = {}
        for record in intents:
            if (not isinstance(record, dict) or record.get("project_id") != self.project_id
                    or not isinstance(record.get("resource"), dict)):
                raise StoreError("invalid operation intent export")
            if record.get("scan_id") in intent_by_scan:
                raise StoreError("duplicate operation intent in export")
            intent_by_scan[record["scan_id"]] = record
        reconciliation_by_id = {}
        for record in reconciliations:
            if (not isinstance(record, dict) or record.get("project_id") != self.project_id
                    or not isinstance(record.get("result"), dict)
                    or record.get("outcome") not in {"SUCCEEDED", "FAILED"}):
                raise StoreError("invalid operation reconciliation export")
            intent = intent_by_scan.get(record.get("scan_id"))
            expected_state = "RECONCILED_SUCCEEDED" if record.get("outcome") == "SUCCEEDED" else "RECONCILED_FAILED"
            if (intent is None or intent.get("source_id") != record.get("source_id")
                    or intent.get("state") != expected_state):
                raise StoreError("reconciliation has no matching terminal operation intent")
            if record.get("reconciliation_id") in reconciliation_by_id:
                raise StoreError("duplicate reconciliation id in export")
            reconciliation_by_id[record["reconciliation_id"]] = record
        coverage_by_scan = {}
        coverage_state_by_scan = {}
        for record in coverage:
            if not isinstance(record, dict) or record.get("project_id") != self.project_id:
                raise StoreError("coverage project does not match destination store")
            scan_id, source_id = record.get("scan_id"), record.get("source_id")
            if not isinstance(scan_id, str) or not scan_id or not isinstance(source_id, str) or not source_id:
                raise StoreError("coverage record has invalid identifiers")
            if scan_id in coverage_by_scan:
                raise StoreError("duplicate scan_id in import bundle")
            coverage_by_scan[scan_id] = source_id
            coverage_state_by_scan[scan_id] = record.get("coverage_state")
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
        measurement_by_id = {record.get("measurement_id"): record for record in measurements if isinstance(record, dict)}
        link_keys = set()
        for link in reconciliation_measurement_links:
            if not isinstance(link, dict):
                raise StoreError("invalid reconciliation measurement link")
            event = reconciliation_by_id.get(link.get("reconciliation_id"))
            measurement = measurement_by_id.get(link.get("measurement_id"))
            key = (link.get("reconciliation_id"), link.get("kind"))
            if (event is None or event.get("outcome") != "SUCCEEDED" or measurement is None
                    or event.get("scan_id") != link.get("scan_id")
                    or event.get("source_id") != link.get("source_id")
                    or measurement.get("scan_id") != link.get("scan_id")
                    or measurement.get("source_id") != link.get("source_id")
                    or measurement.get("kind") != link.get("kind") or key in link_keys
                    or coverage_by_scan.get(link.get("scan_id")) != link.get("source_id")
                    or coverage_state_by_scan.get(link.get("scan_id")) != "INDETERMINATE"
                    or measurement.get("coverage_state") not in {"COMPLETE", "PARTIAL"}
                    or measurement.get("coverage_state") != event.get("result", {}).get("coverage_state")
                    or event.get("result", {}).get("measurements", {}).get(link.get("kind")) != measurement.get("value")
                    or measurement.get("measured_at") != event.get("recorded_at")
                    or measurement.get("source_timestamp") != event.get("result", {}).get("source_timestamp")
                    or measurement.get("evidence_ref") != event.get("result", {}).get("evidence_ref")
                    or measurement.get("confidence") != "UNVERIFIED"
                    or measurement.get("method") != f"obis_v0.2_status_reconciliation:{link.get('reconciliation_id')}"):
                raise StoreError("reconciliation measurement link does not match its original indeterminate coverage, event, and measurement")
            link_keys.add(key)

        inserted = 0
        with closing(self._connect()) as db:
            with db:
                for record in intents:
                    existing = db.execute("SELECT * FROM operation_intents WHERE scan_id=?", (record["scan_id"],)).fetchone()
                    normalized = {**record, "resource_json": json.dumps(record["resource"], sort_keys=True, separators=(",", ":"))}
                    normalized.pop("resource", None)
                    if existing:
                        if dict(existing) != normalized:
                            raise StoreError("conflicting duplicate operation intent")
                        continue
                    db.execute(
                        """INSERT INTO operation_intents
                           (scan_id,operation_id,idempotency_key,project_id,source_id,peer_id,
                            principal_ref,capability_id,capability_version,resource_json,
                            payload_sha256,request_hash,state,created_at,updated_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (record["scan_id"],record["operation_id"],record["idempotency_key"],
                         record["project_id"],record["source_id"],record["peer_id"],record["principal_ref"],
                         record["capability_id"],record["capability_version"],
                         json.dumps(record["resource"],sort_keys=True,separators=(",", ":")),
                         record["payload_sha256"],record["request_hash"],record["state"],
                         record["created_at"],record["updated_at"]),
                    )
                    inserted += 1
                for record in coverage:
                    existing = db.execute("SELECT * FROM coverage WHERE scan_id=?", (record["scan_id"],)).fetchone()
                    normalized_record = {**record, "schema_version": record.get("schema_version", "0.1"), "limitations": record.get("limitations", [])}
                    if existing:
                        current = dict(existing)
                        current["limitations"] = json.loads(current.pop("limitations_json"))
                        if current != normalized_record:
                            raise StoreError("conflicting duplicate scan_id in destination store")
                        continue
                    db.execute("INSERT INTO coverage (scan_id,schema_version,project_id,source_id,requested_scope,coverage_state,started_at,finished_at,actor_id,adapter_id,adapter_version,items_seen,pages_seen,reason_code,limitations_json,checkpoint_ref) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", self._coverage_values(normalized_record))
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
                for record in reconciliations:
                    existing = db.execute(
                        "SELECT * FROM operation_reconciliations WHERE reconciliation_id=?",
                        (record["reconciliation_id"],),
                    ).fetchone()
                    normalized = {**record, "result": record.get("result", {})}
                    if existing:
                        current = dict(existing)
                        current["result"] = json.loads(current.pop("result_json"))
                        if current != normalized:
                            raise StoreError("conflicting duplicate reconciliation")
                        continue
                    db.execute(
                        """INSERT INTO operation_reconciliations
                           (reconciliation_id,scan_id,project_id,source_id,outcome,recorded_at,result_json)
                           VALUES (?,?,?,?,?,?,?)""",
                        (record["reconciliation_id"],record["scan_id"],record["project_id"],
                         record["source_id"],record["outcome"],record["recorded_at"],
                         json.dumps(record["result"],sort_keys=True,separators=(",",":"),ensure_ascii=False)),
                    )
                    inserted += 1
                for link in reconciliation_measurement_links:
                    existing = db.execute(
                        """SELECT * FROM reconciliation_measurement_links
                           WHERE reconciliation_id=? AND kind=?""",
                        (link["reconciliation_id"],link["kind"]),
                    ).fetchone()
                    if existing:
                        if dict(existing) != link:
                            raise StoreError("conflicting duplicate reconciliation measurement link")
                        continue
                    db.execute(
                        """INSERT INTO reconciliation_measurement_links
                           (reconciliation_id,measurement_id,scan_id,source_id,kind)
                           VALUES (?,?,?,?,?)""",
                        (link["reconciliation_id"],link["measurement_id"],link["scan_id"],link["source_id"],link["kind"]),
                    )
                    inserted += 1
        return inserted
