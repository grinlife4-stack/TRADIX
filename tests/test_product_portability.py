import copy
import hashlib
import json
from pathlib import Path

from scripts.check_product_portability import assess_portability, validate_manifest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "examples" / "hello-world" / "portability.json"
EVIDENCE_SHA = "a" * 64


def load_manifest():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def make_release_ready(manifest, evidence_dir):
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_file = evidence_dir / "portability-evidence.json"
    evidence_file.write_text('{"restore":"passed","integrity":"verified"}\\n', encoding="utf-8")
    evidence_sha = hashlib.sha256(evidence_file.read_bytes()).hexdigest()
    evidence_path = evidence_file.name

    manifest["status"] = "verified"
    for name in ("source", "runtime", "artifacts", "secrets", "backup_restore"):
        manifest[name]["status"] = "verified"
        manifest[name]["evidence_path"] = evidence_path
        manifest[name]["evidence_sha256"] = evidence_sha
    for dependency in manifest["dependencies"]:
        dependency["status"] = "verified"
        dependency["evidence_path"] = evidence_path
        dependency["evidence_sha256"] = evidence_sha
    for data_asset in manifest["data_assets"]:
        data_asset["status"] = "verified"
        data_asset["evidence_path"] = evidence_path
        data_asset["evidence_sha256"] = evidence_sha
    manifest["backup_restore"]["restore_test"] = {
        "status": "passed",
        "target": "isolated-secondary-host",
        "tested_at": "2026-11-17T12:00:00Z",
        "evidence_path": evidence_path,
        "evidence_sha256": evidence_sha,
    }
    manifest["exit_cost"] = {
        "status": "estimated",
        "currency": "USD",
        "estimated_amount": 125.0,
        "estimated_hours": 3.5,
        "notes": "Estimate from a completed isolated restore rehearsal.",
        "evidence_path": evidence_path,
        "evidence_sha256": evidence_sha,
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


def test_windows_absolute_evidence_paths_are_rejected_on_posix():
    manifest = load_manifest()
    manifest["source"].update({
        "status": "verified",
        "evidence_sha256": EVIDENCE_SHA,
        "evidence_path": "C:\\\\private\\\\evidence.json",
    })

    errors = validate_manifest(manifest)

    assert "source.evidence_path must be a safe relative path when status is verified" in errors


def test_secrets_must_be_excluded_from_source_control_and_exports():
    manifest = load_manifest()
    manifest["secrets"]["export_excluded"] = False

    errors = validate_manifest(manifest)

    assert "secrets.export_excluded must be true" in errors


def test_unknown_secret_fields_are_rejected():
    manifest = load_manifest()
    manifest["secrets"]["secret_value"] = "must-never-be-in-a-portability-manifest"

    errors = validate_manifest(manifest)

    assert any("secrets has unknown fields" in error for error in errors)


def test_verified_component_requires_sha256_evidence():
    manifest = load_manifest()
    manifest["source"]["status"] = "verified"

    errors = validate_manifest(manifest)

    assert "source.evidence_sha256 is required when status is verified" in errors


def test_verified_evidence_paths_cannot_escape_the_manifest_directory():
    manifest = load_manifest()
    manifest["source"].update({
        "status": "verified",
        "evidence_path": "../outside.json",
        "evidence_sha256": EVIDENCE_SHA,
    })

    errors = validate_manifest(manifest)

    assert "source.evidence_path must be a safe relative path when status is verified" in errors


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
    assert "a passed restore test must include a safe relative evidence_path" in errors


def test_release_ready_requires_all_verified_sections_and_a_real_restore_record(tmp_path):
    manifest = make_release_ready(load_manifest(), tmp_path)

    report = assess_portability(manifest, "release", tmp_path)

    assert report["status"] == "RELEASE_READY"
    assert report["release_ready"] is True
    assert report["errors"] == []
    assert report["release_blockers"] == []


def test_estimated_exit_cost_requires_file_backed_evidence():
    manifest = load_manifest()
    manifest["exit_cost"].update({
        "status": "estimated",
        "estimated_amount": 10,
        "estimated_hours": 1,
    })

    errors = validate_manifest(manifest)

    assert "exit_cost.evidence_sha256 is required when status is estimated or verified" in errors
    assert "exit_cost.evidence_path must be a safe relative path when status is estimated or verified" in errors


def test_non_finite_exit_cost_is_rejected():
    manifest = load_manifest()
    manifest["exit_cost"].update({
        "status": "estimated",
        "estimated_amount": float("nan"),
        "estimated_hours": 2,
    })

    errors = validate_manifest(manifest)

    assert any("finite non-negative estimated_amount" in error for error in errors)


def test_release_evidence_hash_must_match_the_actual_file(tmp_path):
    manifest = make_release_ready(load_manifest(), tmp_path)
    (tmp_path / "portability-evidence.json").write_text("tampered\\n", encoding="utf-8")

    report = assess_portability(manifest, "release", tmp_path)

    assert report["status"] == "BLOCKED"
    assert any("SHA-256 does not match" in error for error in report["errors"])


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
