"""Fail-closed candidate gate. Passing analysis never places an order."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Literal

from .economics import UnitEconomicsInput, UnitEconomicsResult, calculate_unit_economics
from .evidence import Evidence, EvidenceAssessment, EvidencePolicy, assess_evidence


DecisionStatus = Literal["hold", "reject", "eligible_for_manual_pilot"]


@dataclass(frozen=True, slots=True)
class Candidate:
    candidate_id: str
    economics: UnitEconomicsInput
    evidence: tuple[Evidence, ...] = ()

    def __post_init__(self) -> None:
        if not self.candidate_id.strip():
            raise ValueError("candidate_id cannot be empty")


@dataclass(frozen=True, slots=True)
class CandidatePolicy:
    minimum_net_profit: Decimal = Decimal("0")
    minimum_net_margin: Decimal = Decimal("0.15")
    evidence_policy: EvidencePolicy = field(default_factory=EvidencePolicy)

    def __post_init__(self) -> None:
        if not self.minimum_net_profit.is_finite() or self.minimum_net_profit < 0:
            raise ValueError("minimum_net_profit must be finite and non-negative")
        if (
            not self.minimum_net_margin.is_finite()
            or self.minimum_net_margin < 0
            or self.minimum_net_margin >= 1
        ):
            raise ValueError("minimum_net_margin must be in the range [0, 1)")


@dataclass(frozen=True, slots=True)
class CandidateDecision:
    candidate_id: str
    status: DecisionStatus
    reasons: tuple[str, ...]
    economics: UnitEconomicsResult
    evidence: EvidenceAssessment


def evaluate_candidate(
    candidate: Candidate,
    policy: CandidatePolicy,
    now: datetime,
) -> CandidateDecision:
    """Return a review status only; this function has no commerce side effects."""

    economics = calculate_unit_economics(candidate.economics)
    evidence = assess_evidence(candidate.evidence, policy.evidence_policy, now)

    if (
        economics.net_profit.amount <= policy.minimum_net_profit
        or economics.net_margin < policy.minimum_net_margin
    ):
        return CandidateDecision(
            candidate_id=candidate.candidate_id,
            status="reject",
            reasons=("unit economics do not meet the configured profit and margin thresholds",),
            economics=economics,
            evidence=evidence,
        )

    if not evidence.ready:
        reasons = tuple(
            reason
            for reason, values in (
                ("required evidence is missing", evidence.missing),
                ("evidence is stale", evidence.stale),
                ("evidence is not verified", evidence.unverified),
                ("evidence timestamp is in the future", evidence.future_dated),
            )
            if values
        )
        return CandidateDecision(
            candidate_id=candidate.candidate_id,
            status="hold",
            reasons=reasons,
            economics=economics,
            evidence=evidence,
        )

    return CandidateDecision(
        candidate_id=candidate.candidate_id,
        status="eligible_for_manual_pilot",
        reasons=("analysis gates passed; manual review and separate operational approval remain required",),
        economics=economics,
        evidence=evidence,
    )
