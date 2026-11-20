"""Offline-first, read-only ECOSCAN runtime (stdlib only).

This module intentionally has no network client, external process launcher, provider adapter,
or source-file write operation. It records metadata measurements only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 1
EXPORT_VERSION = 1
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
STATUSES = {"COMPLETE", "EMPTY", "PARTIAL", "DISABLED"}


class EcoscanError(Exception):
    """Invalid registry, unsafe source, or persistence/export failure."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _safe_id(value: Any, field: str) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise EcoscanError(f"invalid {field}: expected a safe identifier")
    return value


def load_registry(path: str | Path) -> tuple[dict[str, Any], Path]:
    registry_path = Path(path).expanduser().resolve()
    try:
        config = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EcoscanError(f"cannot read registry: {exc}") from exc
    if not isinstance(config, dict) or config.get("schema_version") != SCHEMA_VERSION:
        raise EcoscanError("unsupported registry schema_version")
    if not isinstance(config.get("system_enabled", True), bool):
        raise EcoscanError("system_enabled must be boolean")
    projects = config.get("projects")
    if not isinstance(projects, list):
        raise EcoscanError("projects must be an array")
    seen_projects: set[str] = set()
    seen_sources: set[str] = set()
    for project in projects:
        if not isinstance(project, dict):
            raise EcoscanError("project entries must be objects")
        pid = _safe_id(project.get("project_id"), "project_id")
        if pid in seen_projects:
            raise EcoscanError(f"duplicate project_id: {pid}")
        seen_projects.add(pid)
        if not isinstance(project.get("enabled", True), bool):
            raise EcoscanError(f"project {pid}: enabled must be boolean")
        sources = project.get("sources", [])
        if not isinstance(sources, list):
            raise EcoscanError(f"project {pid}: sources must be an array")
        for source in sources:
            if not isinstance(source, dict):
                raise EcoscanError(f"project {pid}: source entries must be objects")
            sid = _safe_id(source.get("source_id"), "source_id")
            if sid in seen_sources:
                raise EcoscanError(f"duplicate source_id: {sid}")
            seen_sources.add(sid)
            if source.get("provider") != "filesystem_local":
                raise EcoscanError(f"source {sid}: phase 1 accepts filesystem_local only")
            if not isinstance(source.get("enabled", True), bool):
                raise EcoscanError(f"source {sid}: enabled must be boolean")
            if not isinstance(source.get("path"), str) or not source["path"].strip():
                raise EcoscanError(f"source {sid}: path must be a non-empty string")
    return config, registry_path.parent


def select_sources(config: dict[str, Any], scope: str = "ecosystem", project_id: str | None = None, source_id: str | None = None) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    if scope not in {"ecosystem", "project", "source"}:
        raise EcoscanError("scope must be ecosystem, project, or source")
    if scope == "ecosystem" and (project_id or source_id):
        raise EcoscanError("ecosystem scope does not accept selectors")
    if scope == "project" and (not project_id or source_id):
        raise EcoscanError("project scope requires only --project")
    if scope == "source" and (not source_id or project_id):
        raise EcoscanError("source scope requires only --source")
    projects = config["projects"]
    if project_id and not any(p["project_id"] == project_id for p in projects):
        raise EcoscanError(f"unknown project_id: {project_id}")
    all_sources = [(p, s) for p in projects for s in p.get("sources", [])]
    if source_id and not any(s["source_id"] == source_id for _, s in all_sources):
        raise EcoscanError(f"unknown source_id: {source_id}")
    if scope == "project":
        return [(p, s) for p, s in all_sources if p["project_id"] == project_id]
    if scope == "source":
        return [(p, s) for p, s in all_sources if s["source_id"] == source_id]
    return all_sources


def _walk_metadata(root: Path) -> tuple[int, int, list[str]]:
    """Return file_count, byte_count and bounded warnings without opening files."""
    cursor = root.absolute()
    while cursor != cursor.parent:
        if cursor.is_symlink():
            raise EcoscanError("source path must not contain symbolic-link components")
        cursor = cursor.parent
    if not root.exists() or not root.is_dir():
        raise EcoscanError("source path is missing or is not a directory")
    file_count = byte_count = 0
    warnings: list[str] = []

    def record_walk_error(exc: OSError) -> None:
        warnings.append("DIRECTORY_METADATA_UNAVAILABLE")

    for current, dirs, files in os.walk(root, topdown=True, onerror=record_walk_error, followlinks=False):
        current_path = Path(current)
        safe_dirs = []
        for name in dirs:
            candidate = current_path / name
            try:
                if candidate.is_symlink():
                    warnings.append("SYMLINK_DIRECTORY_SKIPPED")
                else:
                    safe_dirs.append(name)
            except OSError:
                warnings.append("DIRECTORY_METADATA_UNAVAILABLE")
        dirs[:] = safe_dirs
        for name in files:
            candidate = current_path / name
            try:
                info = candidate.lstat()
                if candidate.is_symlink() or not candidate.is_file():
                    warnings.append("NON_REGULAR_FILE_SKIPPED")
                    continue
                file_count += 1
                byte_count += info.st_size
            except OSError:
                warnings.append("FILE_METADATA_UNAVAILABLE")
    return file_count, byte_count, sorted(set(warnings))


def scan_source(project: dict[str, Any], source: dict[str, Any], registry_dir: Path) -> dict[str, Any]:
    measured_at = utc_now()
    run_id = str(uuid.uuid4())
    if not project.get("enabled", True) or not source.get("enabled", True):
        return {"run_id": run_id, "project_id": project["project_id"], "source_id": source["source_id"], "status": "DISABLED", "file_count": None, "bytes": None, "measured_at": measured_at, "source_label": Path(source["path"]).name or "local-source", "warnings": ["DISABLED_BY_REGISTRY"]}
    configured = Path(source["path"]).expanduser()
    root = configured if configured.is_absolute() else (registry_dir / configured)
    try:
        file_count, byte_count, warnings = _walk_metadata(root.absolute())
        status = "PARTIAL" if warnings else ("EMPTY" if file_count == 0 else "COMPLETE")
    except (OSError, EcoscanError):
        file_count, byte_count, warnings, status = None, None, ["SOURCE_UNAVAILABLE"], "PARTIAL"
    return {"run_id": run_id, "project_id": project["project_id"], "source_id": source["source_id"], "status": status, "file_count": file_count, "bytes": byte_count, "measured_at": measured_at, "source_label": Path(source["path"]).name or "local-source", "warnings": warnings}


def database_path(database_dir: str | Path, project_id: str) -> Path:
    pid = _safe_id(project_id, "project_id")
    return Path(database_dir).expanduser().resolve() / f"{pid}.sqlite3"


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=10000")
    db.execute("""CREATE TABLE IF NOT EXISTS measurements (
        run_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, source_id TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('COMPLETE','EMPTY','PARTIAL','DISABLED')),
        file_count INTEGER, bytes INTEGER, measured_at TEXT NOT NULL,
        source_label TEXT NOT NULL, warnings_json TEXT NOT NULL,
        CHECK(file_count IS NULL OR file_count >= 0), CHECK(bytes IS NULL OR bytes >= 0)
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_measurements_project_time ON measurements(project_id, measured_at)")
    return db


def persist_measurements(database_dir: str | Path, project_id: str, records: Iterable[dict[str, Any]]) -> Path:
    path = database_path(database_dir, project_id)
    with _connect(path) as db:
        for record in records:
            if record["project_id"] != project_id:
                raise EcoscanError("measurement project_id does not match database owner")
            db.execute("""INSERT INTO measurements VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(run_id) DO NOTHING""", (record["run_id"], record["project_id"], record["source_id"], record["status"], record["file_count"], record["bytes"], record["measured_at"], record["source_label"], json.dumps(record["warnings"], ensure_ascii=False)))
    return path


def read_measurements(database_dir: str | Path, project_id: str) -> list[dict[str, Any]]:
    path = database_path(database_dir, project_id)
    if not path.exists():
        return []
    with _connect(path) as db:
        rows = db.execute("SELECT run_id,project_id,source_id,status,file_count,bytes,measured_at,source_label,warnings_json FROM measurements ORDER BY measured_at,run_id").fetchall()
    return [{"run_id": r[0], "project_id": r[1], "source_id": r[2], "status": r[3], "file_count": r[4], "bytes": r[5], "measured_at": r[6], "source_label": r[7], "warnings": json.loads(r[8])} for r in rows]


def export_project(database_dir: str | Path, project_id: str, output_dir: str | Path, fmt: str = "both") -> list[Path]:
    if fmt not in {"json", "jsonl", "both"}:
        raise EcoscanError("format must be json, jsonl, or both")
    records = read_measurements(database_dir, project_id)
    target = Path(output_dir).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    manifest = {"export_version": EXPORT_VERSION, "project_id": project_id, "exported_at": utc_now(), "record_count": len(records)}
    paths: list[Path] = []
    if fmt in {"json", "both"}:
        path = target / f"{project_id}.json"
        path.write_text(json.dumps({"manifest": manifest, "measurements": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        paths.append(path)
    if fmt in {"jsonl", "both"}:
        path = target / f"{project_id}.jsonl"
        lines = [json.dumps({"type": "manifest", **manifest}, ensure_ascii=False)]
        lines.extend(json.dumps({"type": "measurement", **record}, ensure_ascii=False) for record in records)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        paths.append(path)
    return paths


def _validate_record(record: dict[str, Any], project_id: str) -> None:
    if not isinstance(record, dict) or record.get("project_id") != project_id:
        raise EcoscanError("invalid measurement project ownership")
    _safe_id(record.get("source_id"), "source_id")
    _safe_id(record.get("run_id"), "run_id")
    if record.get("status") not in STATUSES:
        raise EcoscanError("invalid measurement status")
    for field in ("bytes", "file_count"):
        value = record.get(field)
        if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
            raise EcoscanError(f"invalid {field}")
    if not isinstance(record.get("measured_at"), str) or not isinstance(record.get("warnings"), list):
        raise EcoscanError("invalid measurement metadata")


def import_export(path: str | Path, database_dir: str | Path, project_id: str) -> int:
    source = Path(path)
    try:
        raw = source.read_text(encoding="utf-8")
        if source.suffix.lower() == ".jsonl":
            objects = [json.loads(line) for line in raw.splitlines() if line.strip()]
            if not objects or objects[0].get("type") != "manifest":
                raise EcoscanError("JSONL export is missing manifest")
            manifest = objects[0]
            records = [{k: v for k, v in obj.items() if k != "type"} for obj in objects[1:] if obj.get("type") == "measurement"]
        else:
            payload = json.loads(raw)
            manifest, records = payload.get("manifest", {}), payload.get("measurements", [])
    except (OSError, UnicodeError, json.JSONDecodeError, AttributeError) as exc:
        raise EcoscanError(f"invalid export file: {exc}") from exc
    if manifest.get("export_version") != EXPORT_VERSION or manifest.get("project_id") != project_id or manifest.get("record_count") != len(records):
        raise EcoscanError("export manifest mismatch")
    for record in records:
        _validate_record(record, project_id)
    before = len(read_measurements(database_dir, project_id))
    persist_measurements(database_dir, project_id, records)
    after = len(read_measurements(database_dir, project_id))
    return after - before


def run_scan(config: dict[str, Any], registry_dir: Path, database_dir: str | Path, output_dir: str | Path, scope: str = "ecosystem", project_id: str | None = None, source_id: str | None = None, fmt: str = "both") -> dict[str, Any]:
    if not config.get("system_enabled", True):
        return {"status": "DISABLED", "measurements": [], "exports": []}
    selected = select_sources(config, scope, project_id, source_id)
    by_project: dict[str, list[dict[str, Any]]] = {}
    for project, source in selected:
        record = scan_source(project, source, registry_dir)
        by_project.setdefault(project["project_id"], []).append(record)
    exports: list[str] = []
    for pid, records in by_project.items():
        persist_measurements(database_dir, pid, records)
        exports.extend(str(p) for p in export_project(database_dir, pid, output_dir, fmt))
    statuses = [r["status"] for records in by_project.values() for r in records]
    overall = "PARTIAL" if any(s == "PARTIAL" for s in statuses) else ("DISABLED" if statuses and all(s == "DISABLED" for s in statuses) else "COMPLETE")
    return {"status": overall, "measurements": [r for records in by_project.values() for r in records], "exports": exports}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ECOSCAN offline local read-only inventory")
    parser.add_argument("--config", default="tools/ecoscan/config/local-registry.json")
    parser.add_argument("--scope", choices=["ecosystem", "project", "source"], default="ecosystem")
    parser.add_argument("--project")
    parser.add_argument("--source")
    parser.add_argument("--database-dir")
    parser.add_argument("--output-dir")
    parser.add_argument("--format", choices=["json", "jsonl", "both"], default="both")
    parser.add_argument("--import", dest="import_file")
    parser.add_argument("--import-project")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config, registry_dir = load_registry(args.config)
        database_dir = args.database_dir or config.get("database_dir", ".ecoscan/db")
        output_dir = args.output_dir or config.get("output_dir", ".ecoscan/exports")
        if args.import_file:
            if not args.import_project:
                raise EcoscanError("--import requires --import-project")
            count = import_export(args.import_file, database_dir, args.import_project)
            print(json.dumps({"imported_records": count, "project_id": args.import_project}))
            return 0
        report = run_scan(config, registry_dir, database_dir, output_dir, args.scope, args.project, args.source, args.format)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2 if report["status"] == "PARTIAL" else 0
    except EcoscanError as exc:
        print(f"ECOSCAN: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
