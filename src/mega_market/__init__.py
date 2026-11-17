"""Independent Mega Market product-analysis core."""

from .catalog import (
    IngestionReport,
    ListingObservation,
    MarketDataAdapter,
    ProductCluster,
    SourceDescriptor,
    SourcePermissionError,
    SourceRegistry,
    collect_listings,
    group_product_listings,
    is_valid_gtin,
    product_identity_key,
)
from .decision import Candidate, CandidateDecision, CandidatePolicy, evaluate_candidate
from .demand import DemandAssessment, DemandObservation, DemandPolicy, assess_demand
from .economics import Money, UnitEconomicsInput, UnitEconomicsResult, calculate_unit_economics
from .evidence import Evidence, EvidenceAssessment, EvidencePolicy, assess_evidence

__all__ = [
    "Candidate",
    "CandidateDecision",
    "CandidatePolicy",
    "DemandAssessment",
    "DemandObservation",
    "DemandPolicy",
    "Evidence",
    "EvidenceAssessment",
    "EvidencePolicy",
    "IngestionReport",
    "ListingObservation",
    "MarketDataAdapter",
    "Money",
    "ProductCluster",
    "SourceDescriptor",
    "SourcePermissionError",
    "SourceRegistry",
    "UnitEconomicsInput",
    "UnitEconomicsResult",
    "assess_demand",
    "assess_evidence",
    "calculate_unit_economics",
    "collect_listings",
    "evaluate_candidate",
    "group_product_listings",
    "is_valid_gtin",
    "product_identity_key",
]

__version__ = "0.3.0"
