import copy
import json
from pathlib import Path

from scripts.check_product_portability import assess_portability, validate_manifest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "examples" / "hello-world" / "portability.json"
EVIDENCE_SHA = "a" * 64


def load_manifest():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def make_release_ready(manifest):
    manifest["status"] = "verified"
    for name in ("source", "runtime", "artifacts", "secrets", "backup_restore"):
        manifest[name]["status"] = "verified"
        manifest[name]["evidence_sha256"] = EVIDENCE_SHA
    for dependency in manifest["dependencies"]:
        dependency["status"] = "verified"
        dependency["evidence_sha256"] = EVIDENCE_SHA
    for data_asset in manifest["data_assets"]:
        data_asset["status"] = "verified"
        data_asset["evidence_sha256"] = EVIDENCE_SHA
    manifest["backup_restore"]["restore_test"] = {
        "status": "passed",
        "target": "isolated-secondary-host",
        "tested_at": "2026-11-17T12:00:00Z",
        "evidence_sha256": EVIDENCE_SHA,
    }
    manifest["exit_cost"] = {
        "status": "estimated",
        "currency": "USD",
        "estimated_amount": 125.0,
        "estimated_hours": 3.5,
        "notes": "Estimate from a completed isolated restore rehearsal.",
    }
    return manifest


def test_hello_world_portability_manifest_is_design_complete_but_not_release_ready():
    manifest = load_manifest()
    report = assess_portability(manifest, "design")

    assert report["status"] == "DESIGN_READY"
    assert report["design_ready"] is True
    assert report["release_ready"] is False
    assert any("restore test" in item for item in report["release_blockers"])
    assert any("exit cost" in item for item in report["release_blockers"])


def test_release_mode_fails_closed_until_restore_and_exit_cost_are_verified():
    report = assess_portability(load_manifest(), "release")

    assert report["status"] == "BLOCKED"
    assert report["release_ready"] is False


def test_provider_specific_dependency_requires_a_replacement_plan():
    manifest = load_manifest()
    manifest["dependencies"][0]["provider_specific"] = True
    manifest["dependencies"][0]["replacement_plan"] = ""
    manifest["dependencies"][0]["alternatives"] = []

    errors = validate_manifest(manifest)

    assert any("replacement_plan" in error for error in errors)


def test_secrets_must_be_excluded_from_source_control_and_exports():
    manifest = load_manifest()
    manifest["secrets"]["export_excluded"] = False

    errors = validate_manifest(manifest)

    assert "secrets.export_excluded must be true" in errors


def test_verified_component_requires_sha256_evidence():
    manifest = load_manifest()
    manifest["source"]["status"] = "verified"

    errors = validate_manifest(manifest)

    assert "source.evidence_sha256 is required when status is verified" in errors


def test_passed_restore_requires_target_timestamp_and_evidence():
    manifest = load_manifest()
    manifest["backup_restore"]["restore_test"] = {
        "status": "passed",
        "target": "secondary-host",
        "tested_at": "2026-11-17T12:00:00",
    }

    errors = validate_manifest(manifest)

    assert any("timezone-aware tested_at" in error for error in errors)
    assert "a passed restore test must include evidence_sha256" in errors


def test_release_ready_requires_all_verified_sections_and_a_real_restore_record():
    manifest = make_release_ready(load_manifest())

    report = assess_portability(manifest, "release")

    assert report["status"] == "RELEASE_READY"
    assert report["release_ready"] is True
    assert report["errors"] == []
    assert report["release_blockers"] == []


def test_non_finite_exit_cost_is_rejected():
    manifest = load_manifest()
    manifest["exit_cost"].update({
        "status": "estimated",
        "estimated_amount": float("nan"),
        "estimated_hours": 2,
    })

    errors = validate_manifest(manifest)

    assert any("finite non-negative estimated_amount" in error for error in errors)


def test_unknown_top_level_fields_are_rejected():
    manifest = load_manifest()
    manifest["provider_secret"] = "must-not-be-here"

    errors = validate_manifest(manifest)

    assert any("unknown top-level fields" in error for error in errors)


def test_invalid_nested_restore_shape_does_not_crash_release_assessment():
    manifest = copy.deepcopy(load_manifest())
    manifest["backup_restore"]["restore_test"] = None

    report = assess_portability(manifest, "release")

    assert report["status"] == "INVALID"
    assert any("restore_test must be an object" in error for error in report["errors"])
