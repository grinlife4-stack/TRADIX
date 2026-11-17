"""Fail-closed candidate gate. Passing analysis never places an order."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal

from .demand import DemandAssessment
from .economics import UnitEconomicsInput, UnitEconomicsResult, calculate_unit_economics
from .evidence import Evidence, EvidenceAssessment, EvidencePolicy, assess_evidence


DecisionStatus = Literal["hold", "reject", "eligible_for_manual_pilot"]
DemandGate = Literal["proxy_or_direct", "direct_sales_only"]


@dataclass(frozen=True, slots=True)
class Candidate:
    candidate_id: str
    economics: UnitEconomicsInput
    evidence: tuple[Evidence, ...] = ()
    demand_assessment: DemandAssessment | None = None

    def __post_init__(self) -> None:
        if not self.candidate_id.strip():
            raise ValueError("candidate_id cannot be empty")


@dataclass(frozen=True, slots=True)
class CandidatePolicy:
    minimum_net_profit: Decimal = Decimal("0")
    minimum_net_margin: Decimal = Decimal("0.15")
    evidence_policy: EvidencePolicy = field(default_factory=EvidencePolicy)
    minimum_demand_evidence: DemandGate = "proxy_or_direct"
    max_demand_assessment_age: timedelta = timedelta(hours=1)

    def __post_init__(self) -> None:
        if not self.minimum_net_profit.is_finite() or self.minimum_net_profit < 0:
            raise ValueError("minimum_net_profit must be finite and non-negative")
        if (
            not self.minimum_net_margin.is_finite()
            or self.minimum_net_margin < 0
            or self.minimum_net_margin >= 1
        ):
            raise ValueError("minimum_net_margin must be in the range [0, 1)")
        if self.minimum_demand_evidence not in ("proxy_or_direct", "direct_sales_only"):
            raise ValueError("unsupported minimum_demand_evidence policy")
        if self.max_demand_assessment_age <= timedelta(0):
            raise ValueError("max_demand_assessment_age must be greater than zero")


@dataclass(frozen=True, slots=True)
class CandidateDecision:
    candidate_id: str
    status: DecisionStatus
    reasons: tuple[str, ...]
    economics: UnitEconomicsResult
    evidence: EvidenceAssessment
    demand_status: str


def evaluate_candidate(
    candidate: Candidate,
    policy: CandidatePolicy,
    now: datetime,
) -> CandidateDecision:
    """Return a review status only; this function has no commerce side effects."""

    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")

    economics = calculate_unit_economics(candidate.economics)
    evidence = assess_evidence(candidate.evidence, policy.evidence_policy, now)
    demand = candidate.demand_assessment
    demand_status = demand.status if demand is not None else "missing"

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
            demand_status=demand_status,
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
            demand_status=demand_status,
        )

    demand_reasons: list[str] = []
    if demand is None:
        demand_reasons.append("structured demand assessment is missing")
    else:
        age = now - demand.assessed_at
        if age < timedelta(0):
            demand_reasons.append("demand assessment timestamp is in the future")
        elif age > policy.max_demand_assessment_age:
            demand_reasons.append("demand assessment is stale")
        elif demand.status in ("insufficient_evidence", "estimates_only"):
            demand_reasons.append("fresh verified observed demand evidence is unavailable")
        elif (
            policy.minimum_demand_evidence == "direct_sales_only"
            and demand.status != "direct_sales_observations_available"
        ):
            demand_reasons.append("policy requires direct sales observations")

    if demand_reasons:
        return CandidateDecision(
            candidate_id=candidate.candidate_id,
            status="hold",
            reasons=tuple(demand_reasons),
            economics=economics,
            evidence=evidence,
            demand_status=demand_status,
        )

    return CandidateDecision(
        candidate_id=candidate.candidate_id,
        status="eligible_for_manual_pilot",
        reasons=(
            "analysis gates passed; proxy evidence still requires a bounded manual pilot when direct sales data is unavailable",
            "manual review and separate operational approval remain required",
        ),
        economics=economics,
        evidence=evidence,
        demand_status=demand_status,
    )
