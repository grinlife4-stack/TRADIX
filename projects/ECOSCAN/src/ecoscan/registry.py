"""Strict project-registry parsing without runtime third-party dependencies."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from .models import ProjectRegistry, RetentionPolicy, ScanBudget, SourceDescriptor

IDENTIFIER = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")
MEASUREMENT_KINDS = {
    "logical_bytes",
    "allocated_bytes",
    "physical_bytes",
    "capacity_bytes",
    "object_count",
    "file_count",
    "provider_reported_usage",
}
REGISTRY_KEYS = {"schema_version", "project_id", "sources"}
SOURCE_REQUIRED = {
    "source_id", "owner_id", "operator_id", "subsystem_id", "source_type",
    "locator", "adapter_id", "adapter_version", "credential_ref", "enabled",
    "budget", "expected_measurements", "retention_policy", "created_at", "updated_at",
}
SOURCE_OPTIONAL = {"scope_tags"}
BUDGET_KEYS = {"max_pages", "max_items", "timeout_seconds", "max_duration_seconds"}
RETENTION_KEYS = {"history_days", "evidence_days"}


class RegistryError(ValueError):
    """Raised when a registry is malformed or violates a fail-closed invariant."""


def _object(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise RegistryError(f"{name} must be an object")
    return value


def _exact_keys(value: Mapping[str, Any], required: set[str], optional: set[str], name: str) -> None:
    missing = required - value.keys()
    unknown = value.keys() - required - optional
    if missing:
        raise RegistryError(f"{name} is missing required fields: {', '.join(sorted(missing))}")
    if unknown:
        raise RegistryError(f"{name} contains unknown fields: {', '.join(sorted(unknown))}")


def _identifier(value: Any, name: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise RegistryError(f"{name} must be a valid non-empty identifier")
    return value


def _text(value: Any, name: str, maximum: int) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise RegistryError(f"{name} must be a non-empty string of at most {maximum} characters")
    return value


def _integer(value: Any, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise RegistryError(f"{name} must be an integer between {minimum} and {maximum}")
    return value


def _timestamp(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise RegistryError(f"{name} must be an ISO-8601 timestamp")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise RegistryError(f"{name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RegistryError(f"{name} must include a timezone")
    return value


def _parse_source(raw: Any, index: int) -> SourceDescriptor:
    source = _object(raw, f"sources[{index}]")
    _exact_keys(source, SOURCE_REQUIRED, SOURCE_OPTIONAL, f"sources[{index}]")

    budget_raw = _object(source["budget"], f"sources[{index}].budget")
    _exact_keys(budget_raw, BUDGET_KEYS, set(), f"sources[{index}].budget")
    budget = ScanBudget(
        max_pages=_integer(budget_raw["max_pages"], "max_pages", 1, 10_000),
        max_items=_integer(budget_raw["max_items"], "max_items", 1, 10_000_000),
        timeout_seconds=_integer(budget_raw["timeout_seconds"], "timeout_seconds", 1, 300),
        max_duration_seconds=_integer(
            budget_raw["max_duration_seconds"], "max_duration_seconds", 1, 86_400
        ),
    )

    retention_raw = _object(source["retention_policy"], f"sources[{index}].retention_policy")
    _exact_keys(retention_raw, RETENTION_KEYS, set(), f"sources[{index}].retention_policy")
    retention = RetentionPolicy(
        history_days=_integer(retention_raw["history_days"], "history_days", 0, 36_500),
        evidence_days=_integer(retention_raw["evidence_days"], "evidence_days", 0, 36_500),
    )

    credential_ref = source["credential_ref"]
    if credential_ref is not None:
        credential_ref = _text(credential_ref, "credential_ref", 512)
    if type(source["enabled"]) is not bool:
        raise RegistryError("enabled must be a boolean")

    expected = source["expected_measurements"]
    if (
        not isinstance(expected, list)
        or not expected
        or any(not isinstance(item, str) or item not in MEASUREMENT_KINDS for item in expected)
        or len(set(expected)) != len(expected)
    ):
        raise RegistryError("expected_measurements must contain unique supported measurement kinds")

    scope_tags = source.get("scope_tags", [])
    if (
        not isinstance(scope_tags, list)
        or any(not isinstance(tag, str) or not tag or len(tag) > 64 for tag in scope_tags)
        or len(set(scope_tags)) != len(scope_tags)
    ):
        raise RegistryError("scope_tags must contain unique non-empty strings")

    created_at = _timestamp(source["created_at"], "created_at")
    updated_at = _timestamp(source["updated_at"], "updated_at")
    created = datetime.fromisoformat(created_at[:-1] + "+00:00" if created_at.endswith("Z") else created_at)
    updated = datetime.fromisoformat(updated_at[:-1] + "+00:00" if updated_at.endswith("Z") else updated_at)
    if updated < created:
        raise RegistryError("updated_at cannot precede created_at")

    return SourceDescriptor(
        source_id=_identifier(source["source_id"], "source_id"),
        owner_id=_identifier(source["owner_id"], "owner_id"),
        operator_id=_identifier(source["operator_id"], "operator_id"),
        subsystem_id=_identifier(source["subsystem_id"], "subsystem_id"),
        source_type=_text(source["source_type"], "source_type", 64),
        locator=_text(source["locator"], "locator", 2048),
        adapter_id=_text(source["adapter_id"], "adapter_id", 128),
        adapter_version=_text(source["adapter_version"], "adapter_version", 64),
        credential_ref=credential_ref,
        enabled=source["enabled"],
        scope_tags=tuple(scope_tags),
        budget=budget,
        expected_measurements=tuple(expected),
        retention_policy=retention,
        created_at=created_at,
        updated_at=updated_at,
    )


def parse_registry(document: Any) -> ProjectRegistry:
    raw = _object(document, "registry")
    _exact_keys(raw, REGISTRY_KEYS, set(), "registry")
    if raw["schema_version"] != "0.1":
        raise RegistryError("unsupported registry schema_version")
    project_id = _identifier(raw["project_id"], "project_id")
    sources_raw = raw["sources"]
    if not isinstance(sources_raw, list):
        raise RegistryError("sources must be an array")

    sources = tuple(_parse_source(item, index) for index, item in enumerate(sources_raw))
    source_ids = [source.source_id for source in sources]
    if len(source_ids) != len(set(source_ids)):
        raise RegistryError("source_id values must be unique within a project registry")
    return ProjectRegistry("0.1", project_id, sources)


def load_registry(path: str | Path) -> ProjectRegistry:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RegistryError(f"cannot load registry: {type(exc).__name__}") from exc
    return parse_registry(document)
