"""Independent Mega Market product-analysis core."""

from .decision import Candidate, CandidateDecision, CandidatePolicy, evaluate_candidate
from .economics import Money, UnitEconomicsInput, UnitEconomicsResult, calculate_unit_economics
from .evidence import Evidence, EvidenceAssessment, EvidencePolicy, assess_evidence

__all__ = [
    "Candidate",
    "CandidateDecision",
    "CandidatePolicy",
    "Evidence",
    "EvidenceAssessment",
    "EvidencePolicy",
    "Money",
    "UnitEconomicsInput",
    "UnitEconomicsResult",
    "assess_evidence",
    "calculate_unit_economics",
    "evaluate_candidate",
]

__version__ = "0.2.0"
