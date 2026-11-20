import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError


SCHEMA_ROOT = Path(__file__).parents[1] / "standards" / "ecoscan" / "0.1"
FORMAT_CHECKER = FormatChecker()


def load_schema(name: str) -> dict:
    schema = json.loads((SCHEMA_ROOT / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def assert_valid(schema_name: str, instance: dict) -> None:
    Draft202012Validator(
        load_schema(schema_name), format_checker=FORMAT_CHECKER
    ).validate(instance)


def assert_invalid(schema_name: str, instance: dict) -> None:
    validator = Draft202012Validator(
        load_schema(schema_name), format_checker=FORMAT_CHECKER
    )
    with pytest.raises(ValidationError):
        validator.validate(instance)


def test_all_ecoscan_01_schemas_are_valid_json_schema_documents() -> None:
    names = [
        "source-registry.schema.json",
        "measurement.schema.json",
        "coverage.schema.json",
        "export-manifest.schema.json",
    ]
    for name in names:
        load_schema(name)


def test_project_registry_accepts_multiple_sources_and_opaque_credential_references() -> None:
    source = {
        "source_id": "b2-main",
        "owner_id": "owner-a",
        "operator_id": "operator-a",
        "subsystem_id": "storage",
        "source_type": "s3-compatible",
        "locator": "b2://project-a/main",
        "adapter_id": "backblaze-b2",
        "adapter_version": "0.1.0",
        "credential_ref": "secret-manager://project-a/b2-readonly",
        "enabled": True,
        "scope_tags": ["storage"],
        "budget": {
            "max_pages": 20,
            "max_items": 100000,
            "timeout_seconds": 30,
            "max_duration_seconds": 600,
        },
        "expected_measurements": ["logical_bytes", "object_count"],
        "retention_policy": {"history_days": 365, "evidence_days": 30},
        "created_at": "2026-11-20T09:00:00Z",
        "updated_at": "2026-11-20T09:00:00Z",
    }
    registry = {"schema_version": "0.1", "project_id": "project-a", "sources": [source]}
    assert_valid("source-registry.schema.json", registry)
    second = {**source, "source_id": "b2-archive", "subsystem_id": "backups"}
    assert_valid(
        "source-registry.schema.json",
        {**registry, "sources": [source, second]},
    )
    assert_valid(
        "source-registry.schema.json",
        {"schema_version": "0.1", "project_id": "project-a", "sources": []},
    )
    assert_invalid(
        "source-registry.schema.json",
        {**registry, "sources": [{**source, "application_key": "must-never-be-stored"}]},
    )
    assert_invalid(
        "source-registry.schema.json",
        {**registry, "sources": [{**source, "credential_ref": ""}]},
    )
    assert_invalid(
        "source-registry.schema.json",
        {**registry, "sources": [{**source, "subsystem_id": "../other-project"}]},
    )


def test_measurement_schema_preserves_semantics_and_rejects_negative_values() -> None:
    measurement = {
        "schema_version": "0.1",
        "measurement_id": "m-001",
        "project_id": "project-a",
        "source_id": "b2-main",
        "kind": "logical_bytes",
        "value": 1024,
        "unit": "byte",
        "measured_at": "2026-11-20T09:00:00Z",
        "source_timestamp": None,
        "method": "s3-list-objects-v2-current-visible-objects",
        "adapter_id": "backblaze-b2",
        "adapter_version": "0.1.0",
        "coverage_state": "PARTIAL",
        "confidence": "MEDIUM",
        "limitations": ["Noncurrent versions are not included"],
        "evidence_ref": None,
        "checkpoint_ref": "checkpoint-001",
    }
    assert_valid("measurement.schema.json", measurement)
    assert_invalid("measurement.schema.json", {**measurement, "value": -1})
    assert_invalid("measurement.schema.json", {**measurement, "unit": "object"})
    assert_invalid("measurement.schema.json", {**measurement, "value": 1024.5})


def test_coverage_schema_accepts_failed_and_disabled_states() -> None:
    coverage = {
        "schema_version": "0.1",
        "scan_id": "scan-001",
        "project_id": "project-a",
        "source_id": "b2-main",
        "requested_scope": "source:b2-main",
        "coverage_state": "NOT_AUTHORIZED",
        "started_at": "2026-11-20T09:00:00Z",
        "finished_at": "2026-11-20T09:00:01Z",
        "actor_id": "operator-a",
        "adapter_id": "backblaze-b2",
        "adapter_version": "0.1.0",
        "items_seen": 0,
        "pages_seen": 0,
        "reason_code": "credential_missing",
        "limitations": ["No provider request was made"],
        "checkpoint_ref": None,
    }
    assert_valid("coverage.schema.json", coverage)
    assert_invalid("coverage.schema.json", {**coverage, "unexpected": True})
    assert_invalid("coverage.schema.json", {**coverage, "finished_at": None})


def test_export_manifest_requires_hashes_and_excludes_secret_values() -> None:
    manifest = {
        "schema_version": "0.1",
        "export_id": "export-001",
        "project_id": "project-a",
        "exported_at": "2026-11-20T09:00:00Z",
        "included_from": None,
        "included_through": "2026-11-20T09:00:00Z",
        "files": [
            {
                "path": "measurements.jsonl",
                "media_type": "application/x-ndjson",
                "size_bytes": 1024,
                "sha256": "a" * 64,
            }
        ],
        "credential_policy": "secret-values-excluded;credential-references-redacted",
        "source_system": "ECOSCAN 0.1",
    }
    assert_valid("export-manifest.schema.json", manifest)
    assert_invalid("export-manifest.schema.json", {**manifest, "api_key": "secret"})
    for unsafe_path in ("../private/secret.txt", "a/../private.txt", "a/./b.txt", ".", "a//b.txt", "/etc/passwd", "C:/private.txt", "a\\\\b.txt"):
        unsafe = {**manifest, "files": [{**manifest["files"][0], "path": unsafe_path}]}
        assert_invalid("export-manifest.schema.json", unsafe)
