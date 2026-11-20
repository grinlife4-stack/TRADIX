from __future__ import annotations
import json
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
        records = {"coverage": bundle["coverage"], "measurement": bundle["measurements"], "checkpoint": bundle["checkpoints"]}
        for kind in ("coverage", "measurement", "checkpoint"):
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
    }
    if any(manifest.get(key) != value for key, value in counts.items()):
        raise TransferError("export manifest record counts do not match")
    scan_sources = {}
    for record in bundle["coverage"]:
        if not isinstance(record, dict) or record.get("project_id") != project_id:
            raise TransferError("coverage crosses project boundary")
        scan_id, source_id = record.get("scan_id"), record.get("source_id")
        if not isinstance(scan_id, str) or not scan_id or not isinstance(source_id, str) or not source_id:
            raise TransferError("coverage identifiers are invalid")
        if scan_id in scan_sources:
            raise TransferError("duplicate scan_id in export")
        scan_sources[scan_id] = source_id
    measurement_ids = set()
    for record in bundle["measurements"]:
        if not isinstance(record, dict) or record.get("project_id") != project_id:
            raise TransferError("measurement crosses project boundary")
        if scan_sources.get(record.get("scan_id")) != record.get("source_id"):
            raise TransferError("measurement source does not match its coverage record")
        measurement_id = record.get("measurement_id")
        if not isinstance(measurement_id, str) or not measurement_id or measurement_id in measurement_ids:
            raise TransferError("measurement IDs must be present and unique")
        measurement_ids.add(measurement_id)
        value = record.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise TransferError("measurement value must be non-negative numeric data")
    for record in bundle["checkpoints"]:
        if not isinstance(record, dict) or not isinstance(record.get("checkpoint"), dict):
            raise TransferError("invalid checkpoint record")
        if scan_sources.get(record.get("scan_id")) != record.get("source_id"):
            raise TransferError("checkpoint source does not match its coverage record")


def import_store(path: str | Path, store: ProjectStore) -> int:
    source = Path(path)
    try:
        raw = source.read_text(encoding="utf-8")
        if source.suffix.lower() == ".jsonl":
            objects = [json.loads(line) for line in raw.splitlines() if line.strip()]
            if not objects or objects[0].get("type") != "manifest":
                raise TransferError("JSONL export is missing manifest")
            manifest = {key: value for key, value in objects[0].items() if key != "type"}
            bundle = {"coverage": [], "measurements": [], "checkpoints": []}
            for obj in objects[1:]:
                kind = obj.get("type")
                if kind not in {"coverage", "measurement", "checkpoint"}:
                    raise TransferError("unknown JSONL record type")
                key = {"coverage": "coverage", "measurement": "measurements", "checkpoint": "checkpoints"}[kind]
                bundle[key].append({key: value for key, value in obj.items() if key != "type"})
        else:
            payload = json.loads(raw)
            manifest = payload.get("manifest", {})
            bundle = {key: payload.get(key, []) for key in ("coverage", "measurements", "checkpoints")}
    except (OSError, UnicodeError, json.JSONDecodeError, AttributeError) as exc:
        raise TransferError(f"cannot read export: {exc}") from exc
    _validate_bundle(manifest, bundle, store.project_id)
    try:
        return store.import_bundle(bundle)
    except (StoreError, ValueError) as exc:
        raise TransferError(str(exc)) from exc
