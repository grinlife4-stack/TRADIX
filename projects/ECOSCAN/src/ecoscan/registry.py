from __future__ import annotations
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from .models import EcosystemRegistry, ProjectRegistry, RetentionPolicy, ScanBudget, SourceDescriptor

class RegistryError(ValueError):
    pass

ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
PROJECT_KEYS = {"project_id", "sources"}
SOURCE_KEYS = {"source_id", "owner_id", "operator_id", "subsystem_id", "source_type", "locator", "adapter_id", "adapter_version", "credential_ref", "enabled", "scope_tags", "budget", "expected_measurements", "retention_policy", "created_at", "updated_at"}
BUDGET_KEYS = {"max_pages", "max_items", "timeout_seconds", "max_duration_seconds"}
RETENTION_KEYS = {"history_days", "evidence_days"}
KNOWN_MEASUREMENTS = {"logical_bytes", "allocated_bytes", "physical_bytes", "capacity_bytes", "object_count", "file_count", "provider_reported_usage"}

def _identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise RegistryError(f"{field} must be a valid identifier")
    return value

def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise RegistryError(f"{field} must be a timezone-aware ISO-8601 timestamp")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise RegistryError(f"{field} must be a timezone-aware ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RegistryError(f"{field} must include a timezone")
    return parsed

def _exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    unknown = set(value) - expected
    missing = expected - set(value)
    if unknown:
        raise RegistryError(f"{label} contains unknown fields: {', '.join(sorted(unknown))}")
    if missing:
        raise RegistryError(f"{label} is missing fields: {', '.join(sorted(missing))}")

def _parse_project(raw: Any) -> ProjectRegistry:
    if not isinstance(raw, dict):
        raise RegistryError("project entry must be an object")
    _exact_keys(raw, PROJECT_KEYS, "project")
    project_id = _identifier(raw["project_id"], "project_id")
    if not isinstance(raw["sources"], list):
        raise RegistryError("sources must be an array")
    sources = []
    ids = set()
    for item in raw["sources"]:
        if not isinstance(item, dict):
            raise RegistryError("source entry must be an object")
        _exact_keys(item, SOURCE_KEYS, "source")
        sid = _identifier(item["source_id"], "source_id")
        if sid in ids:
            raise RegistryError("source IDs must be unique within a project")
        ids.add(sid)
        for field in ("owner_id", "operator_id", "subsystem_id", "adapter_id", "adapter_version"):
            _identifier(item[field], field)
        if item["source_type"] not in {"filesystem", "obis_bridge"}:
            raise RegistryError("unsupported source_type")
        if not isinstance(item["locator"], str) or not item["locator"].strip():
            raise RegistryError("locator must be a non-empty local path")
        if not isinstance(item["enabled"], bool):
            raise RegistryError("enabled must be boolean")
        if item["credential_ref"] is not None and (not isinstance(item["credential_ref"], str) or not item["credential_ref"]):
            raise RegistryError("credential_ref must be null or a non-empty string")
        tags = item["scope_tags"]
        if not isinstance(tags, list) or any(not isinstance(x, str) or not x for x in tags):
            raise RegistryError("scope_tags must be an array of non-empty strings")
        expected = item["expected_measurements"]
        if not isinstance(expected, list) or not expected or any(not isinstance(x, str) or x not in KNOWN_MEASUREMENTS for x in expected):
            raise RegistryError("expected_measurements must contain known string measurement kinds")
        budget_raw = item["budget"]
        retention_raw = item["retention_policy"]
        if not isinstance(budget_raw, dict):
            raise RegistryError("budget must be an object")
        _exact_keys(budget_raw, BUDGET_KEYS, "budget")
        if not isinstance(retention_raw, dict):
            raise RegistryError("retention_policy must be an object")
        _exact_keys(retention_raw, RETENTION_KEYS, "retention_policy")
        for key, value in budget_raw.items():
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise RegistryError(f"budget.{key} must be a positive integer")
        for key, value in retention_raw.items():
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise RegistryError(f"retention_policy.{key} must be a non-negative integer")
        created = _timestamp(item["created_at"], "created_at")
        updated = _timestamp(item["updated_at"], "updated_at")
        if updated < created:
            raise RegistryError("updated_at must not precede created_at")
        sources.append(SourceDescriptor(
            source_id=sid, owner_id=item["owner_id"], operator_id=item["operator_id"],
            subsystem_id=item["subsystem_id"], source_type=item["source_type"], locator=item["locator"],
            adapter_id=item["adapter_id"], adapter_version=item["adapter_version"],
            credential_ref=item["credential_ref"], enabled=item["enabled"], scope_tags=tuple(tags),
            budget=ScanBudget(**budget_raw), expected_measurements=tuple(expected),
            retention_policy=RetentionPolicy(**retention_raw), created_at=item["created_at"], updated_at=item["updated_at"],
        ))
    return ProjectRegistry(project_id=project_id, sources=tuple(sources))

def parse_registry(payload: Any) -> ProjectRegistry | EcosystemRegistry:
    if not isinstance(payload, dict) or payload.get("schema_version") != "0.1":
        raise RegistryError("unsupported registry schema_version")
    if "project_id" in payload:
        _exact_keys(payload, {"schema_version", "project_id", "sources"}, "registry")
        return _parse_project({"project_id": payload["project_id"], "sources": payload["sources"]})
    _exact_keys(payload, {"schema_version", "projects"}, "ecosystem registry")
    if not isinstance(payload["projects"], list):
        raise RegistryError("projects must be an array")
    projects = tuple(_parse_project(project) for project in payload["projects"])
    ids = [project.project_id for project in projects]
    if len(ids) != len(set(ids)):
        raise RegistryError("project IDs must be unique")
    return EcosystemRegistry(projects=projects)

def load_registry(path: str | Path) -> ProjectRegistry | EcosystemRegistry:
    try:
        payload = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RegistryError(f"cannot load registry: {exc}") from exc
    return parse_registry(payload)
