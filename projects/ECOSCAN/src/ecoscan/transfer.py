from __future__ import annotations
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from .store import ProjectStore, StoreError

EXPORT_VERSION = "0.1"

class TransferError(ValueError):
    pass

def _manifest(store: ProjectStore, bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": EXPORT_VERSION,
        "project_id": store.project_id,
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "coverage_count": len(bundle["coverage"]),
        "measurement_count": len(bundle["measurements"]),
        "checkpoint_count": len(bundle["checkpoints"]),
        "operation_intent_count": len(bundle.get("operation_intents", [])),
        "operation_reconciliation_count": len(bundle.get("operation_reconciliations", [])),
        "reconciliation_measurement_link_count": len(bundle.get("reconciliation_measurement_links", [])),
    }

def export_store(store: ProjectStore, output_dir: str | Path, fmt: str = "both") -> list[Path]:
    if fmt not in {"json", "jsonl", "both"}:
        raise TransferError("format must be json, jsonl, or both")
    target = Path(output_dir).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    bundle = store.export_bundle()
    manifest = _manifest(store, bundle)
    paths = []
    if fmt in {"json", "both"}:
        path = target / f"{store.project_id}.json"
        path.write_text(json.dumps({"manifest": manifest, **bundle}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        paths.append(path)
    if fmt in {"jsonl", "both"}:
        path = target / f"{store.project_id}.jsonl"
        lines = [json.dumps({"type": "manifest", **manifest}, ensure_ascii=False)]
        records = {
            "coverage": bundle["coverage"], "measurement": bundle["measurements"],
            "checkpoint": bundle["checkpoints"],
            "operation_intent": bundle.get("operation_intents", []),
            "operation_reconciliation": bundle.get("operation_reconciliations", []),
            "reconciliation_measurement_link": bundle.get("reconciliation_measurement_links", []),
        }
        for kind in ("coverage", "measurement", "checkpoint", "operation_intent", "operation_reconciliation", "reconciliation_measurement_link"):
            for item in records[kind]:
                lines.append(json.dumps({"type": kind, **item}, ensure_ascii=False))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        paths.append(path)
    return paths

def _validate_bundle(manifest: dict[str, Any], bundle: dict[str, Any], project_id: str) -> None:
    if manifest.get("schema_version") != EXPORT_VERSION or manifest.get("project_id") != project_id:
        raise TransferError("export manifest version or project ownership mismatch")
    for key in ("coverage", "measurements", "checkpoints"):
        if not isinstance(bundle.get(key), list):
            raise TransferError(f"{key} must be an array")
    counts = {
        "coverage_count": len(bundle["coverage"]),
        "measurement_count": len(bundle["measurements"]),
        "checkpoint_count": len(bundle["checkpoints"]),
        "operation_intent_count": len(bundle.get("operation_intents", [])),
        "operation_reconciliation_count": len(bundle.get("operation_reconciliations", [])),
        "reconciliation_measurement_link_count": len(bundle.get("reconciliation_measurement_links", [])),
    }
    if any(manifest.get(key, 0) != value for key, value in counts.items()):
        raise TransferError("export manifest record counts do not match")
    scan_sources = {}
    for record in bundle["coverage"]:
        if not isinstance(record, dict) or record.get("project_id") != project_id:
            raise TransferError("coverage crosses project boundary")
        scan_id, source_id = record.get("scan_id"), record.get("source_id")
        if not isinstance(scan_id, str) or not scan_id or not isinstance(source_id, str) or not source_id:
            raise TransferError("coverage identifiers are invalid")
        if record.get("coverage_state") not in {"COMPLETE", "PARTIAL", "FAILED", "DISABLED", "NOT_AUTHORIZED", "NOT_CONFIGURED", "INDETERMINATE"}:
            raise TransferError("coverage state is invalid")
        if any(isinstance(record.get(key), bool) or not isinstance(record.get(key), int) or record[key] < 0 for key in ("items_seen", "pages_seen")):
            raise TransferError("coverage counters are invalid")
        if scan_id in scan_sources:
            raise TransferError("duplicate scan_id in export")
        scan_sources[scan_id] = source_id
    measurement_ids = set()
    coverage_states = {record["scan_id"]: record["coverage_state"] for record in bundle["coverage"]}
    allowed_units = {"logical_bytes": "byte", "allocated_bytes": "byte", "physical_bytes": "byte", "capacity_bytes": "byte", "object_count": "object", "file_count": "file", "provider_reported_usage": "provider_unit"}
    links = bundle.get("reconciliation_measurement_links", [])
    if not isinstance(links, list):
        raise TransferError("reconciliation_measurement_links must be an array")
    link_by_measurement = {item.get("measurement_id"): item for item in links if isinstance(item, dict)}
    successful_events = {
        item.get("reconciliation_id"): item
        for item in bundle.get("operation_reconciliations", [])
        if isinstance(item, dict) and item.get("outcome") == "SUCCEEDED"
    }
    for record in bundle["measurements"]:
        if not isinstance(record, dict) or record.get("project_id") != project_id:
            raise TransferError("measurement crosses project boundary")
        if scan_sources.get(record.get("scan_id")) != record.get("source_id"):
            raise TransferError("measurement source does not match its coverage record")
        measurement_id = record.get("measurement_id")
        if not isinstance(measurement_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", measurement_id) or measurement_id in measurement_ids:
            raise TransferError("measurement IDs must be valid and unique")
        measurement_ids.add(measurement_id)
        value = record.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value < 0:
            raise TransferError("measurement value must be finite non-negative numeric data")
        kind = record.get("kind")
        if kind not in allowed_units or record.get("unit") != allowed_units[kind]:
            raise TransferError("measurement kind and unit are invalid")
        if record.get("coverage_state") != coverage_states.get(record.get("scan_id")):
            link = link_by_measurement.get(record.get("measurement_id"))
            event = successful_events.get(link.get("reconciliation_id")) if link else None
            if not (
                coverage_states.get(record.get("scan_id")) == "INDETERMINATE"
                and event is not None
                and event.get("scan_id") == record.get("scan_id")
                and event.get("source_id") == record.get("source_id")
                and link.get("scan_id") == record.get("scan_id")
                and link.get("source_id") == record.get("source_id")
                and link.get("kind") == record.get("kind")
            ):
                raise TransferError("measurement coverage state does not match its scan or successful reconciliation link")
        if not isinstance(record.get("measured_at"), str) or not isinstance(record.get("method"), str) or not isinstance(record.get("confidence"), str):
            raise TransferError("measurement metadata is invalid")
    for record in bundle["checkpoints"]:
        if not isinstance(record, dict) or not isinstance(record.get("checkpoint"), dict):
            raise TransferError("invalid checkpoint record")
        if scan_sources.get(record.get("scan_id")) != record.get("source_id"):
            raise TransferError("checkpoint source does not match its coverage record")
    intent_ids = set()
    intent_by_scan = {}
    for record in bundle.get("operation_intents", []):
        if (not isinstance(record, dict) or record.get("project_id") != project_id
                or not isinstance(record.get("resource"), dict)
                or record.get("resource") != {"project_id": project_id, "source_id": record.get("source_id")}
                or record.get("state") not in {"PREPARED", "INDETERMINATE", "RECONCILED_SUCCEEDED", "RECONCILED_FAILED"}
                or not isinstance(record.get("request_hash"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", record["request_hash"])):
            raise TransferError("invalid exported operation intent")
        if record.get("scan_id") in intent_ids:
            raise TransferError("duplicate operation intent")
        intent_ids.add(record["scan_id"])
        intent_by_scan[record["scan_id"]] = record
    reconciliation_ids = set()
    for record in bundle.get("operation_reconciliations", []):
        intent = intent_by_scan.get(record.get("scan_id")) if isinstance(record, dict) else None
        expected_state = "RECONCILED_SUCCEEDED" if isinstance(record, dict) and record.get("outcome") == "SUCCEEDED" else "RECONCILED_FAILED"
        if (not isinstance(record, dict) or record.get("project_id") != project_id
                or record.get("scan_id") not in intent_ids
                or record.get("outcome") not in {"SUCCEEDED", "FAILED"}
                or not isinstance(record.get("result"), dict)
                or intent is None or intent.get("state") != expected_state):
            raise TransferError("invalid operation reconciliation or mismatched terminal intent state")
        if record.get("reconciliation_id") in reconciliation_ids:
            raise TransferError("duplicate operation reconciliation")
        reconciliation_ids.add(record["reconciliation_id"])
    measurement_by_id = {record.get("measurement_id"): record for record in bundle["measurements"]}
    event_by_id = {record.get("reconciliation_id"): record for record in bundle.get("operation_reconciliations", [])}
    link_keys = set()
    for link in bundle.get("reconciliation_measurement_links", []):
        if not isinstance(link, dict):
            raise TransferError("invalid reconciliation measurement link")
        event = event_by_id.get(link.get("reconciliation_id"))
        measurement = measurement_by_id.get(link.get("measurement_id"))
        key = (link.get("reconciliation_id"), link.get("kind"))
        if (event is None or event.get("outcome") != "SUCCEEDED" or measurement is None
                or event.get("scan_id") != link.get("scan_id")
                or event.get("source_id") != link.get("source_id")
                or measurement.get("scan_id") != link.get("scan_id")
                or measurement.get("source_id") != link.get("source_id")
                or measurement.get("kind") != link.get("kind") or key in link_keys
                or scan_sources.get(link.get("scan_id")) != link.get("source_id")
                or coverage_states.get(link.get("scan_id")) != "INDETERMINATE"
                or measurement.get("coverage_state") not in {"COMPLETE", "PARTIAL"}
                or measurement.get("coverage_state") != event.get("result", {}).get("coverage_state")
                or event.get("result", {}).get("measurements", {}).get(link.get("kind")) != measurement.get("value")
                or measurement.get("measured_at") != event.get("recorded_at")
                or measurement.get("source_timestamp") != event.get("result", {}).get("source_timestamp")
                or measurement.get("evidence_ref") != event.get("result", {}).get("evidence_ref")
                or measurement.get("confidence") != "UNVERIFIED"
                or measurement.get("method") != f"obis_v0.2_status_reconciliation:{link.get('reconciliation_id')}"):
            raise TransferError("reconciliation measurement link is inconsistent with original indeterminate coverage")
        link_keys.add(key)


def import_store(path: str | Path, store: ProjectStore) -> int:
    source = Path(path)
    try:
        raw = source.read_text(encoding="utf-8")
        if source.suffix.lower() == ".jsonl":
            objects = [json.loads(line) for line in raw.splitlines() if line.strip()]
            if not objects or objects[0].get("type") != "manifest":
                raise TransferError("JSONL export is missing manifest")
            manifest = {key: value for key, value in objects[0].items() if key != "type"}
            bundle = {"coverage": [], "measurements": [], "checkpoints": [],
                      "operation_intents": [], "operation_reconciliations": [],
                      "reconciliation_measurement_links": []}
            for obj in objects[1:]:
                kind = obj.get("type")
                if kind not in {"coverage", "measurement", "checkpoint", "operation_intent", "operation_reconciliation", "reconciliation_measurement_link"}:
                    raise TransferError("unknown JSONL record type")
                key = {"coverage": "coverage", "measurement": "measurements", "checkpoint": "checkpoints",
                       "operation_intent": "operation_intents",
                       "operation_reconciliation": "operation_reconciliations",
                       "reconciliation_measurement_link": "reconciliation_measurement_links"}[kind]
                bundle[key].append({key: value for key, value in obj.items() if key != "type"})
        else:
            payload = json.loads(raw)
            manifest = payload.get("manifest", {})
            bundle = {key: payload.get(key, []) for key in (
                "coverage", "measurements", "checkpoints", "operation_intents",
                "operation_reconciliations", "reconciliation_measurement_links"
            )}
    except (OSError, UnicodeError, json.JSONDecodeError, AttributeError) as exc:
        raise TransferError(f"cannot read export: {exc}") from exc
    _validate_bundle(manifest, bundle, store.project_id)
    try:
        return store.import_bundle(bundle)
    except (StoreError, ValueError) as exc:
        raise TransferError(str(exc)) from exc
