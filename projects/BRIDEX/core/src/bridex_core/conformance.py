"""Language-neutral OBIS schema-vector runner for BRIDEX tooling."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .manifest import ManifestValidationError, _reject_duplicate_keys


class ConformanceSuiteError(ValueError):
    """Raised when a conformance suite is malformed or a vector fails."""


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (OSError, UnicodeError, json.JSONDecodeError, ManifestValidationError) as exc:
        raise ConformanceSuiteError(f"cannot load strict JSON: {path}") from exc


def run_schema_suite(suite_path: str | Path) -> dict[str, Any]:
    """Run versioned accept/reject vectors against the suite's declared JSON Schema."""
    suite_file = Path(suite_path).resolve(strict=True)
    suite = _load_json(suite_file)
    suite_schema_path = suite_file.parent / "suite.schema.json"
    suite_schema = _load_json(suite_schema_path)
    Draft202012Validator.check_schema(suite_schema)
    suite_errors = list(Draft202012Validator(suite_schema).iter_errors(suite))
    if suite_errors:
        raise ConformanceSuiteError("suite structure is invalid: " + "; ".join(error.message for error in suite_errors))

    schema_path = (suite_file.parent / suite["schema"]).resolve(strict=True)
    try:
        schema_path.relative_to(suite_file.parent.parent.resolve(strict=True))
    except ValueError as exc:
        raise ConformanceSuiteError("declared message schema escapes the OBIS version directory") from exc
    message_schema = _load_json(schema_path)
    Draft202012Validator.check_schema(message_schema)
    validator = Draft202012Validator(message_schema)

    accepted = rejected = 0
    failures: list[str] = []
    for vector in suite["vectors"]:
        actual = "accept" if validator.is_valid(vector["message"]) else "reject"
        expected = vector["expected"]
        if actual != expected:
            failures.append(f"{vector['id']}: expected {expected}, got {actual}")
        if actual == "accept":
            accepted += 1
        else:
            rejected += 1
    if failures:
        raise ConformanceSuiteError("; ".join(failures))
    return {
        "suite_version": suite["suite_version"],
        "protocol_version": suite["protocol_version"],
        "vectors": len(suite["vectors"]),
        "accepted": accepted,
        "rejected": rejected,
        "result": "passed",
    }
