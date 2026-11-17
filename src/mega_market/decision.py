"""Fail-closed candidate gate. Passing analysis never places an order."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal
from .demand import DIRECT_SALES_METRICS, DemandAssessment
from .economics import UnitEconomicsInput, UnitEconomicsResult, calculate_unit_economics
from .evidence import Evidence, EvidenceAssessment, EvidencePolicy, assess_evidence

DecisionStatus = Literal["hold", "reject", "eligible_for_manual_pilot"]

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
    max_demand_assessment_age: timedelta = timedelta(hours=1)
    def __post_init__(self) -> None:
        if not self.minimum_net_profit.is_finite() or self.minimum_net_profit < 0:
            raise ValueError("minimum_net_profit must be finite and non-negative")
        if not self.minimum_net_margin.is_finite() or self.minimum_net_margin < 0 or self.minimum_net_margin >= 1:
            raise ValueError("minimum_net_margin must be in the range [0, 1)")
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

def evaluate_candidate(candidate: Candidate, policy: CandidatePolicy, now: datetime) -> CandidateDecision:
    """Return a review status only; this function has no commerce side effects."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    economics = calculate_unit_economics(candidate.economics)
    evidence = assess_evidence(candidate.evidence, policy.evidence_policy, now)
    demand = candidate.demand_assessment
    demand_status = demand.status if demand is not None else "missing"

    if economics.net_profit.amount <= policy.minimum_net_profit or economics.net_margin < policy.minimum_net_margin:
        return CandidateDecision(candidate.candidate_id, "reject",
            ("unit economics do not meet the configured profit and margin thresholds",),
            economics, evidence, demand_status)

    if not evidence.ready:
        reasons = tuple(reason for reason, values in (
            ("required evidence is missing", evidence.missing),
            ("evidence is stale", evidence.stale),
            ("evidence is not verified", evidence.unverified),
            ("evidence timestamp is in the future", evidence.future_dated),
        ) if values)
        return CandidateDecision(candidate.candidate_id, "hold", reasons, economics, evidence, demand_status)

    demand_reasons: list[str] = []
    if demand is None:
        demand_reasons.append("structured demand assessment is missing")
    else:
        age = now - demand.assessed_at
        if age < timedelta(0):
            demand_reasons.append("demand assessment timestamp is in the future")
        elif age > policy.max_demand_assessment_age:
            demand_reasons.append("demand assessment is stale")
        else:
            positive_sales = tuple(
                item for item in demand.usable_observations
                if item.metric in DIRECT_SALES_METRICS and item.value > 0
            )
            if not positive_sales:
                demand_reasons.append(
                    "fresh verified positive direct-sales observations are required; "
                    "rank, search, reviews, stockouts, and estimates are discovery-only"
                )

    if demand_reasons:
        return CandidateDecision(candidate.candidate_id, "hold", tuple(demand_reasons),
                                 economics, evidence, demand_status)

    return CandidateDecision(
        candidate.candidate_id,
        "eligible_for_manual_pilot",
        (
            "fresh verified positive direct-sales observations and configured analysis gates passed",
            "manual review and separate operational approval remain required; this is not authorization to scale",
        ),
        economics, evidence, demand_status,
    )
