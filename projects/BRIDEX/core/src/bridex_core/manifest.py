"""Standalone validation for owner-exportable BRIDEX package manifests."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


class ManifestValidationError(ValueError):
    """Raised when a Bridge package manifest is malformed or invalid."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ManifestValidationError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def load_schema() -> dict[str, Any]:
    """Load the schema bundled with this independently installable package."""
    schema_path = files("bridex_core").joinpath("schemas/bridge-package-manifest.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def validate_manifest(manifest: Any) -> dict[str, Any]:
    """Validate an already parsed manifest and return it unchanged."""
    validator = Draft202012Validator(load_schema())
    errors = sorted(validator.iter_errors(manifest), key=lambda error: tuple(str(p) for p in error.absolute_path))
    if errors:
        details = []
        for error in errors:
            location = ".".join(str(part) for part in error.absolute_path) or "$"
            details.append(f"{location}: {error.message}")
        raise ManifestValidationError("; ".join(details))
    return manifest


def load_manifest(path: str | Path) -> dict[str, Any]:
    """Read strict UTF-8 JSON, reject duplicate keys, then validate the manifest."""
    try:
        parsed = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except ManifestValidationError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestValidationError("manifest file is unreadable or invalid JSON") from exc
    return validate_manifest(parsed)
