"""Fail-closed design and release gate for product portability manifests.

Design mode checks that a product has documented export, import, dependency,
secret, backup, and exit-cost plans. Release mode additionally requires verified
evidence and a successful restore test on a second isolated target.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any


COMPONENTS = ("source", "runtime", "artifacts", "secrets", "backup_restore")
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
TOP_LEVEL_KEYS = {
    "schema_version", "product_key", "product_type", "status", "source",
    "runtime", "dependencies", "data_assets", "artifacts", "secrets",
    "backup_restore", "exit_cost",
}


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def _aware_datetime(value: Any) -> bool:
    if not _nonempty(value):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _verified_evidence(section: dict[str, Any], label: str, errors: list[str]) -> None:
    if section.get("status") == "verified":
        if not _valid_sha256(section.get("evidence_sha256")):
            errors.append(f"{label}.evidence_sha256 is required when status is verified")
        evidence_path = section.get("evidence_path")
        if not _nonempty(evidence_path) or Path(evidence_path).is_absolute() or ".." in Path(evidence_path).parts:
            errors.append(f"{label}.evidence_path must be a safe relative path when status is verified")


def validate_manifest(manifest: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return ["manifest root must be an object"]

    unknown = sorted(set(manifest) - TOP_LEVEL_KEYS)
    missing = sorted(TOP_LEVEL_KEYS - set(manifest))
    if unknown:
        errors.append(f"unknown top-level fields: {', '.join(unknown)}")
    if missing:
        errors.append(f"missing top-level fields: {', '.join(missing)}")
        return errors

    if manifest.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    product_key = manifest.get("product_key")
    if not isinstance(product_key, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,79}", product_key):
        errors.append("product_key must be a stable lowercase identifier")
    if not _nonempty(manifest.get("product_type")):
        errors.append("product_type must be a non-empty string")
    if manifest.get("status") not in {"planned", "partial", "verified"}:
        errors.append("status must be planned, partial, or verified")

    for name in COMPONENTS:
        section = manifest.get(name)
        if not isinstance(section, dict):
            errors.append(f"{name} must be an object")
            continue
        if section.get("status") not in {"planned", "partial", "verified"}:
            errors.append(f"{name}.status must be planned, partial, or verified")
        _verified_evidence(section, name, errors)

    source = manifest.get("source")
    if isinstance(source, dict):
        for field in ("format", "export_procedure", "import_procedure"):
            if not _nonempty(source.get(field)):
                errors.append(f"source.{field} must be documented")

    runtime = manifest.get("runtime")
    if isinstance(runtime, dict):
        for field in ("interface", "version_policy", "build_definition"):
            if not _nonempty(runtime.get(field)):
                errors.append(f"runtime.{field} must be documented")
        targets = runtime.get("target_matrix")
        if not isinstance(targets, list) or not targets or not all(_nonempty(item) for item in targets):
            errors.append("runtime.target_matrix must list at least one supported target")

    dependencies = manifest.get("dependencies")
    if not isinstance(dependencies, list):
        errors.append("dependencies must be an array")
    else:
        for index, dependency in enumerate(dependencies):
            label = f"dependencies[{index}]"
            if not isinstance(dependency, dict):
                errors.append(f"{label} must be an object")
                continue
            for field in ("name", "kind", "adapter", "replacement_plan"):
                if not _nonempty(dependency.get(field)):
                    errors.append(f"{label}.{field} must be documented")
            if not isinstance(dependency.get("provider_specific"), bool):
                errors.append(f"{label}.provider_specific must be boolean")
            alternatives = dependency.get("alternatives", [])
            if not isinstance(alternatives, list) or not all(_nonempty(item) for item in alternatives):
                errors.append(f"{label}.alternatives must be an array of non-empty strings")
            if dependency.get("status") not in {"planned", "partial", "verified"}:
                errors.append(f"{label}.status must be planned, partial, or verified")
            _verified_evidence(dependency, label, errors)

    data_assets = manifest.get("data_assets")
    if not isinstance(data_assets, list) or not data_assets:
        errors.append("data_assets must contain at least one exportable data class")
    else:
        for index, item in enumerate(data_assets):
            label = f"data_assets[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{label} must be an object")
                continue
            for field in ("name", "format", "export_procedure", "import_procedure", "integrity_method"):
                if not _nonempty(item.get(field)):
                    errors.append(f"{label}.{field} must be documented")
            if item.get("status") not in {"planned", "partial", "verified"}:
                errors.append(f"{label}.status must be planned, partial, or verified")
            _verified_evidence(item, label, errors)

    artifacts = manifest.get("artifacts")
    if isinstance(artifacts, dict):
        for field in ("interface", "export_procedure", "import_procedure", "integrity_method"):
            if not _nonempty(artifacts.get(field)):
                errors.append(f"artifacts.{field} must be documented")

    secrets = manifest.get("secrets")
    if isinstance(secrets, dict):
        if secrets.get("source_control_excluded") is not True:
            errors.append("secrets.source_control_excluded must be true")
        if secrets.get("export_excluded") is not True:
            errors.append("secrets.export_excluded must be true")
        if not _nonempty(secrets.get("rebind_procedure")):
            errors.append("secrets.rebind_procedure must be documented")

    backup = manifest.get("backup_restore")
    if isinstance(backup, dict):
        for field in ("backup_format", "restore_procedure"):
            if not _nonempty(backup.get(field)):
                errors.append(f"backup_restore.{field} must be documented")
        restore_test = backup.get("restore_test")
        if not isinstance(restore_test, dict):
            errors.append("backup_restore.restore_test must be an object")
        else:
            status = restore_test.get("status")
            if status not in {"not_run", "passed", "failed"}:
                errors.append("backup_restore.restore_test.status must be not_run, passed, or failed")
            if status == "passed":
                if not _nonempty(restore_test.get("target")):
                    errors.append("a passed restore test must identify its isolated target")
                if not _aware_datetime(restore_test.get("tested_at")):
                    errors.append("a passed restore test must include a timezone-aware tested_at")
                if not _valid_sha256(restore_test.get("evidence_sha256")):
                    errors.append("a passed restore test must include evidence_sha256")
                evidence_path = restore_test.get("evidence_path")
                if not _nonempty(evidence_path) or Path(evidence_path).is_absolute() or ".." in Path(evidence_path).parts:
                    errors.append("a passed restore test must include a safe relative evidence_path")

    exit_cost = manifest.get("exit_cost")
    if isinstance(exit_cost, dict):
        if not re.fullmatch(r"[A-Z]{3}", str(exit_cost.get("currency", ""))):
            errors.append("exit_cost.currency must be a three-letter uppercase currency code")
        if not _nonempty(exit_cost.get("notes")):
            errors.append("exit_cost.notes must explain the estimate or why it is unknown")
        status = exit_cost.get("status")
        if status not in {"unknown", "estimated", "verified"}:
            errors.append("exit_cost.status must be unknown, estimated, or verified")
        amount = exit_cost.get("estimated_amount")
        hours = exit_cost.get("estimated_hours")
        if status in {"estimated", "verified"}:
            if not isinstance(amount, (int, float)) or isinstance(amount, bool) or not math.isfinite(amount) or amount < 0:
                errors.append("estimated exit cost requires a finite non-negative estimated_amount")
            if not isinstance(hours, (int, float)) or isinstance(hours, bool) or not math.isfinite(hours) or hours < 0:
                errors.append("estimated exit cost requires finite non-negative estimated_hours")
            _verified_evidence(exit_cost, "exit_cost", errors)
        elif amount is not None or hours is not None:
            errors.append("unknown exit cost must use null amount and hours")

    return errors


def verify_evidence_files(manifest: Any, base_dir: Path | None) -> list[str]:
    if base_dir is None:
        return ["release assessment requires the manifest directory to verify evidence files"]
    root = base_dir.resolve()
    errors: list[str] = []

    def walk(value: Any, label: str) -> None:
        if isinstance(value, dict):
            status = value.get("status")
            requires_evidence = status in {"verified", "estimated", "passed"}
            if requires_evidence and "evidence_sha256" in value:
                relative_path = value.get("evidence_path")
                if not _nonempty(relative_path):
                    errors.append(f"{label}.evidence_path is missing")
                elif Path(relative_path).is_absolute() or ".." in Path(relative_path).parts:
                    errors.append(f"{label}.evidence_path escapes the manifest directory")
                else:
                    evidence_file = (root / relative_path).resolve()
                    try:
                        evidence_file.relative_to(root)
                    except ValueError:
                        errors.append(f"{label}.evidence_path escapes the manifest directory")
                    else:
                        if not evidence_file.is_file():
                            errors.append(f"{label} evidence file does not exist: {relative_path}")
                        else:
                            actual = hashlib.sha256(evidence_file.read_bytes()).hexdigest()
                            if actual != value.get("evidence_sha256"):
                                errors.append(f"{label} evidence SHA-256 does not match the file")
            for key, child in value.items():
                walk(child, f"{label}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{label}[{index}]")

    walk(manifest, "manifest")
    return errors


def release_blockers(manifest: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if manifest.get("status") != "verified":
        blockers.append("product portability status is not verified")

    for name in COMPONENTS:
        section = manifest.get(name, {})
        if not isinstance(section, dict) or section.get("status") != "verified":
            blockers.append(f"{name} is not verified")

    for group_name in ("dependencies", "data_assets"):
        items = manifest.get(group_name, [])
        if isinstance(items, list):
            for index, item in enumerate(items):
                if not isinstance(item, dict) or item.get("status") != "verified":
                    blockers.append(f"{group_name}[{index}] is not verified")

    backup = manifest.get("backup_restore", {})
    restore_test = backup.get("restore_test", {}) if isinstance(backup, dict) else {}
    if not isinstance(restore_test, dict) or restore_test.get("status") != "passed":
        blockers.append("restore test has not passed on a second isolated target")

    exit_cost = manifest.get("exit_cost", {})
    if (
        not isinstance(exit_cost, dict)
        or exit_cost.get("status") not in {"estimated", "verified"}
        or exit_cost.get("estimated_amount") is None
        or exit_cost.get("estimated_hours") is None
    ):
        blockers.append("exit cost and effort have not been estimated")

    return blockers


def assess_portability(
    manifest: Any, mode: str = "design", base_dir: Path | None = None
) -> dict[str, Any]:
    if mode not in {"design", "release"}:
        raise ValueError("mode must be design or release")
    errors = validate_manifest(manifest)
    evidence_errors = verify_evidence_files(manifest, base_dir) if mode == "release" else []
    blockers = release_blockers(manifest) if isinstance(manifest, dict) else ["manifest is not an object"]
    design_ready = not errors
    release_ready = design_ready and not evidence_errors and not blockers
    all_errors = errors + evidence_errors
    if errors:
        status = "INVALID"
    elif mode == "design":
        status = "DESIGN_READY"
    else:
        status = "RELEASE_READY" if release_ready else "BLOCKED"
    return {
        "mode": mode,
        "status": status,
        "design_ready": design_ready,
        "release_ready": release_ready,
        "errors": all_errors,
        "release_blockers": blockers + evidence_errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--mode", choices=("design", "release"), default="design")
    args = parser.parse_args()

    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "INVALID", "errors": [str(error)]}, indent=2))
        return 1

    report = assess_portability(manifest, args.mode, args.manifest.resolve().parent)
    print(json.dumps(report, indent=2))
    if args.mode == "design":
        return 0 if report["design_ready"] else 1
    return 0 if report["release_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
