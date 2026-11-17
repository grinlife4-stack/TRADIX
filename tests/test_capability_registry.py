from pathlib import Path

import pytest

from tradix.capabilities import (
    Capability,
    CapabilityRegistry,
    CapabilityReview,
    PromotionBlocked,
)


def sample_capability(scope: str = "shared") -> Capability:
    return Capability(
        capability_id="artifact-manifest",
        version="1.0.0",
        origin_project="sample-product",
        owner="factory-maintainer",
        scope=scope,
        summary="Create and verify portable artifact manifests.",
        interface="manifest.create(input_path) -> manifest",
        tests_ref="tests/test_manifest.py",
        changelog="Initial validated implementation.",
        compatibility="Python >=3.11; stable JSON schema v1.",
        deprecation="At least two minor releases notice.",
        evidence_ref="ci://sample-product/run/123",
    )


def complete_review(**overrides: object) -> CapabilityReview:
    values = {
        "security_passed": True,
        "license_cleared": True,
        "cost_assessed": True,
        "tests_passed": True,
        "compatibility_passed": True,
        "owner_approved": True,
        "external_project_use_case": "second-product/issue/42",
    }
    values.update(overrides)
    return CapabilityReview(**values)


def test_proposal_is_persisted_and_starts_proposed(tmp_path: Path) -> None:
    db = tmp_path / "registry.sqlite"
    registry = CapabilityRegistry(db)
    registry.propose(sample_capability(), actor="reviewer")

    reopened = CapabilityRegistry(db)
    record = reopened.get("artifact-manifest", "1.0.0")
    assert record["status"] == "proposed"
    assert record["origin_project"] == "sample-product"


def test_promotion_requires_every_gate(tmp_path: Path) -> None:
    registry = CapabilityRegistry(tmp_path / "registry.sqlite")
    registry.propose(sample_capability(), actor="reviewer")

    with pytest.raises(PromotionBlocked, match="license_cleared"):
        registry.promote(
            "artifact-manifest",
            "1.0.0",
            complete_review(license_cleared=False),
            actor="approver",
        )


def test_promotion_requires_cross_project_evidence_or_factory_need(
    tmp_path: Path,
) -> None:
    registry = CapabilityRegistry(tmp_path / "registry.sqlite")
    registry.propose(sample_capability(), actor="reviewer")

    with pytest.raises(PromotionBlocked, match="second-project"):
        registry.promote(
            "artifact-manifest",
            "1.0.0",
            complete_review(external_project_use_case="", factory_need_reference=""),
            actor="approver",
        )


def test_product_specific_capability_cannot_be_promoted(tmp_path: Path) -> None:
    registry = CapabilityRegistry(tmp_path / "registry.sqlite")
    registry.propose(sample_capability(scope="product_specific"), actor="reviewer")

    with pytest.raises(PromotionBlocked, match="product-specific"):
        registry.promote(
            "artifact-manifest",
            "1.0.0",
            complete_review(),
            actor="approver",
        )


def test_accepted_capability_cannot_be_promoted_twice(tmp_path: Path) -> None:
    registry = CapabilityRegistry(tmp_path / "registry.sqlite")
    registry.propose(sample_capability(), actor="reviewer")
    registry.promote(
        "artifact-manifest", "1.0.0", complete_review(), actor="approver"
    )

    with pytest.raises(PromotionBlocked, match="only proposed"):
        registry.promote(
            "artifact-manifest", "1.0.0", complete_review(), actor="approver"
        )


def test_event_history_is_append_only_and_deprecation_is_explicit(
    tmp_path: Path,
) -> None:
    db = tmp_path / "registry.sqlite"
    registry = CapabilityRegistry(db)
    registry.propose(sample_capability(), actor="reviewer")
    registry.promote(
        "artifact-manifest", "1.0.0", complete_review(), actor="approver"
    )
    registry.deprecate(
        "artifact-manifest", "1.0.0", actor="maintainer", reason="replaced by v2"
    )

    assert registry.get("artifact-manifest", "1.0.0")["status"] == "deprecated"
    with pytest.raises(PromotionBlocked, match="cannot transition"):
        registry.deprecate(
            "artifact-manifest", "1.0.0", actor="maintainer", reason="duplicate"
        )


def test_duplicate_version_and_invalid_version_are_rejected(tmp_path: Path) -> None:
    registry = CapabilityRegistry(tmp_path / "registry.sqlite")
    with pytest.raises(ValueError, match="MAJOR.MINOR.PATCH"):
        registry.propose(
            Capability(
                **{**sample_capability().__dict__, "version": "latest"}
            ),
            actor="reviewer",
        )

    registry.propose(sample_capability(), actor="reviewer")
    with pytest.raises(Exception):
        registry.propose(sample_capability(), actor="reviewer")


def test_empty_required_fields_fail_closed(tmp_path: Path) -> None:
    registry = CapabilityRegistry(tmp_path / "registry.sqlite")
    with pytest.raises(ValueError, match="owner"):
        registry.propose(
            Capability(
                **{**sample_capability().__dict__, "owner": " "}
            ),
            actor="reviewer",
        )
