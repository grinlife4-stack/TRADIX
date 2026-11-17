"""Metric-specific demand evidence; deliberately no cross-metric score or aggregation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
import re
from typing import Literal


DemandMetric = Literal[
    "transaction_count",
    "units_sold",
    "bestseller_rank",
    "search_interest_index",
    "review_count",
    "stockout_rate",
    "estimated_units_sold",
    "estimated_revenue",
    "advertising_attributed_sales_estimate",
]

OBSERVED_METRICS = frozenset(
    {
        "transaction_count",
        "units_sold",
        "bestseller_rank",
        "search_interest_index",
        "review_count",
        "stockout_rate",
    }
)
ESTIMATED_METRICS = frozenset(
    {
        "estimated_units_sold",
        "estimated_revenue",
        "advertising_attributed_sales_estimate",
    }
)
DIRECT_SALES_METRICS = frozenset({"transaction_count", "units_sold"})
_MARKET_CODE = re.compile(r"^[A-Z]{2}$")


@dataclass(frozen=True, slots=True)
class DemandObservation:
    product_identity_key: str
    source_id: str
    source_record_id: str
    market_code: str
    metric: DemandMetric
    value: Decimal
    unit: str
    observed_at: datetime
    window_start: datetime
    window_end: datetime
    verified: bool
    reference: str | None = None

    def __post_init__(self) -> None:
        if not self.product_identity_key.strip():
            raise ValueError("product_identity_key cannot be empty")
        if not self.source_id.strip() or not self.source_record_id.strip():
            raise ValueError("source identifiers cannot be empty")
        if not _MARKET_CODE.fullmatch(self.market_code):
            raise ValueError("market_code must be an uppercase two-letter code")
        if self.metric not in OBSERVED_METRICS and self.metric not in ESTIMATED_METRICS:
            raise ValueError("unsupported demand metric")
        if not isinstance(self.value, Decimal):
            raise TypeError("demand values must use Decimal; floats are not accepted")
        if not self.value.is_finite() or self.value < 0:
            raise ValueError("demand value must be finite and non-negative")
        if self.metric == "bestseller_rank" and self.value < 1:
            raise ValueError("bestseller_rank must be at least 1")
        if not self.unit.strip():
            raise ValueError("unit cannot be empty")
        timestamps = (self.observed_at, self.window_start, self.window_end)
        if any(item.tzinfo is None or item.utcoffset() is None for item in timestamps):
            raise ValueError("all demand timestamps must be timezone-aware")
        if self.window_start > self.window_end:
            raise ValueError("window_start cannot be after window_end")
        if self.window_end > self.observed_at:
            raise ValueError("measurement window cannot end after observed_at")
        if self.verified and (self.reference is None or not self.reference.strip()):
            raise ValueError("verified observations require a provenance reference")


@dataclass(frozen=True, slots=True)
class DemandPolicy:
    max_age: timedelta = timedelta(hours=24)

    def __post_init__(self) -> None:
        if self.max_age <= timedelta(0):
            raise ValueError("max_age must be greater than zero")


@dataclass(frozen=True, slots=True)
class DemandAssessment:
    status: Literal[
        "direct_sales_observations_available",
        "proxy_observations_only",
        "estimates_only",
        "insufficient_evidence",
    ]
    usable_observations: tuple[DemandObservation, ...]
    stale_metrics: tuple[str, ...]
    unverified_metrics: tuple[str, ...]
    future_metrics: tuple[str, ...]
    ignored_other_product_or_market: int
    direct_sales_metrics: tuple[str, ...]
    proxy_metrics: tuple[str, ...]
    estimate_metrics: tuple[str, ...]
    observed_source_ids: tuple[str, ...]
    estimated_source_ids: tuple[str, ...]
    assessed_at: datetime

    def __post_init__(self) -> None:
        if self.assessed_at.tzinfo is None or self.assessed_at.utcoffset() is None:
            raise ValueError("assessed_at must be timezone-aware")


def assess_demand(
    observations: tuple[DemandObservation, ...],
    product_identity_key: str,
    market_code: str,
    policy: DemandPolicy,
    now: datetime,
) -> DemandAssessment:
    """Classify available evidence without inventing a demand score or sales volume."""

    if not product_identity_key.strip():
        raise ValueError("product_identity_key cannot be empty")
    if not _MARKET_CODE.fullmatch(market_code):
        raise ValueError("market_code must be an uppercase two-letter code")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")

    relevant = tuple(
        item
        for item in observations
        if item.product_identity_key == product_identity_key and item.market_code == market_code
    )
    ignored = len(observations) - len(relevant)

    stale: set[str] = set()
    unverified: set[str] = set()
    future: set[str] = set()
    usable: list[DemandObservation] = []

    for item in relevant:
        if item.observed_at > now or item.window_end > now:
            future.add(item.metric)
            continue
        if now - item.observed_at > policy.max_age:
            stale.add(item.metric)
            continue
        if not item.verified:
            unverified.add(item.metric)
            continue
        usable.append(item)

    direct = tuple(sorted({item.metric for item in usable if item.metric in DIRECT_SALES_METRICS}))
    proxy = tuple(sorted({item.metric for item in usable if item.metric in OBSERVED_METRICS and item.metric not in DIRECT_SALES_METRICS}))
    estimates = tuple(sorted({item.metric for item in usable if item.metric in ESTIMATED_METRICS}))

    if direct:
        status = "direct_sales_observations_available"
    elif proxy:
        status = "proxy_observations_only"
    elif estimates:
        status = "estimates_only"
    else:
        status = "insufficient_evidence"

    usable.sort(key=lambda item: (item.metric, item.source_id, item.source_record_id))
    return DemandAssessment(
        status=status,
        usable_observations=tuple(usable),
        stale_metrics=tuple(sorted(stale)),
        unverified_metrics=tuple(sorted(unverified)),
        future_metrics=tuple(sorted(future)),
        ignored_other_product_or_market=ignored,
        direct_sales_metrics=direct,
        proxy_metrics=proxy,
        estimate_metrics=estimates,
        observed_source_ids=tuple(sorted({item.source_id for item in usable if item.metric in OBSERVED_METRICS})),
        estimated_source_ids=tuple(sorted({item.source_id for item in usable if item.metric in ESTIMATED_METRICS})),
        assessed_at=now,
    )
