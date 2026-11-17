"""Freshness and provenance gate for market and supplier evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


DEFAULT_REQUIRED_EVIDENCE = (
    "demand_signal",
    "market_price",
    "supplier_offer",
    "shipping_quote",
    "direct_fulfillment_authorization",
    "compliance_review",
)


@dataclass(frozen=True, slots=True)
class Evidence:
    evidence_type: str
    source_id: str
    observed_at: datetime
    verified: bool
    reference: str | None = None

    def __post_init__(self) -> None:
        if not self.evidence_type.strip():
            raise ValueError("evidence_type cannot be empty")
        if not self.source_id.strip():
            raise ValueError("source_id cannot be empty")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class EvidencePolicy:
    required_types: tuple[str, ...] = DEFAULT_REQUIRED_EVIDENCE
    max_age: timedelta = timedelta(hours=24)

    def __post_init__(self) -> None:
        if not self.required_types or any(not item.strip() for item in self.required_types):
            raise ValueError("required_types must contain non-empty evidence type names")
        if self.max_age <= timedelta(0):
            raise ValueError("max_age must be greater than zero")


@dataclass(frozen=True, slots=True)
class EvidenceAssessment:
    ready: bool
    missing: tuple[str, ...]
    stale: tuple[str, ...]
    unverified: tuple[str, ...]
    future_dated: tuple[str, ...]


def assess_evidence(
    evidence: tuple[Evidence, ...],
    policy: EvidencePolicy,
    now: datetime,
) -> EvidenceAssessment:
    """Require at least one fresh, verified record for every required evidence type."""

    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")

    missing: list[str] = []
    stale: list[str] = []
    unverified: list[str] = []
    future_dated: list[str] = []

    for required_type in policy.required_types:
        matching = [item for item in evidence if item.evidence_type == required_type]
        if not matching:
            missing.append(required_type)
            continue

        usable = [
            item
            for item in matching
            if item.verified and timedelta(0) <= now - item.observed_at <= policy.max_age
        ]
        if usable:
            continue

        if any(not item.verified for item in matching):
            unverified.append(required_type)
        if any(item.verified and now - item.observed_at > policy.max_age for item in matching):
            stale.append(required_type)
        if any(item.observed_at > now for item in matching):
            future_dated.append(required_type)

    return EvidenceAssessment(
        ready=not (missing or stale or unverified or future_dated),
        missing=tuple(sorted(set(missing))),
        stale=tuple(sorted(set(stale))),
        unverified=tuple(sorted(set(unverified))),
        future_dated=tuple(sorted(set(future_dated))),
    )
