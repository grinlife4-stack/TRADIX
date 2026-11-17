from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from mega_market.demand import DemandObservation, DemandPolicy, assess_demand


NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
WINDOW_START = NOW - timedelta(hours=1)


def observation(
    metric: str = "units_sold",
    value: str = "12",
    *,
    product: str = "gtin:04006381333931",
    market: str = "DE",
    source: str = "market-a",
    observed_at: datetime = NOW,
    verified: bool = True,
    reference: str | None = "source-record://1",
) -> DemandObservation:
    return DemandObservation(
        product_identity_key=product,
        source_id=source,
        source_record_id=f"{source}-record",
        market_code=market,
        metric=metric,  # type: ignore[arg-type]
        value=Decimal(value),
        unit="units",
        observed_at=observed_at,
        window_start=observed_at - timedelta(hours=1),
        window_end=observed_at,
        verified=verified,
        reference=reference,
    )


def assess(*items: DemandObservation):
    return assess_demand(
        tuple(items),
        "gtin:04006381333931",
        "DE",
        DemandPolicy(),
        NOW,
    )


def test_direct_sales_observations_are_distinguished_from_proxy_signals() -> None:
    result = assess(
        observation("units_sold", "12"),
        observation("bestseller_rank", "34", source="market-b"),
        observation("search_interest_index", "78", source="market-c"),
    )
    assert result.status == "direct_sales_observations_available"
    assert result.direct_sales_metrics == ("units_sold",)
    assert result.proxy_metrics == ("bestseller_rank", "search_interest_index")
    assert len(result.usable_observations) == 3


def test_rank_and_search_interest_are_only_proxy_observations() -> None:
    result = assess(
        observation("bestseller_rank", "34"),
        observation("search_interest_index", "78", source="market-b"),
    )
    assert result.status == "proxy_observations_only"
    assert result.direct_sales_metrics == ()


def test_estimates_never_become_observed_sales() -> None:
    result = assess(
        observation("estimated_units_sold", "500"),
        observation("advertising_attributed_sales_estimate", "900", source="market-b"),
    )
    assert result.status == "estimates_only"
    assert result.direct_sales_metrics == ()
    assert result.proxy_metrics == ()
    assert result.estimate_metrics == (
        "advertising_attributed_sales_estimate",
        "estimated_units_sold",
    )


def test_stale_observations_are_not_usable() -> None:
    result = assess(
        observation("units_sold", "12", observed_at=NOW - timedelta(days=3)),
    )
    assert result.status == "insufficient_evidence"
    assert result.stale_metrics == ("units_sold",)
    assert result.usable_observations == ()


def test_unverified_observations_are_not_usable() -> None:
    result = assess(
        observation("units_sold", "12", verified=False, reference=None),
    )
    assert result.status == "insufficient_evidence"
    assert result.unverified_metrics == ("units_sold",)


def test_future_observations_are_not_usable() -> None:
    result = assess(
        observation("units_sold", "12", observed_at=NOW + timedelta(minutes=5)),
    )
    assert result.status == "insufficient_evidence"
    assert result.future_metrics == ("units_sold",)


def test_other_product_and_market_observations_are_ignored() -> None:
    result = assess(
        observation(product="other-product"),
        observation(market="FR", source="market-b"),
    )
    assert result.status == "insufficient_evidence"
    assert result.ignored_other_product_or_market == 2


def test_observation_values_are_not_summed_across_metric_types() -> None:
    result = assess(
        observation("units_sold", "12"),
        observation("bestseller_rank", "34", source="market-b"),
        observation("search_interest_index", "78", source="market-c"),
    )
    assert len(result.usable_observations) == 3
    assert not hasattr(result, "demand_score")
    assert not hasattr(result, "estimated_monthly_sales")


def test_verified_observation_requires_provenance_reference() -> None:
    with pytest.raises(ValueError, match="provenance reference"):
        observation(reference=None)


def test_demand_values_reject_floats() -> None:
    with pytest.raises(TypeError, match="Decimal"):
        DemandObservation(
            product_identity_key="product-1",
            source_id="source",
            source_record_id="record",
            market_code="DE",
            metric="units_sold",
            value=1.5,  # type: ignore[arg-type]
            unit="units",
            observed_at=NOW,
            window_start=WINDOW_START,
            window_end=NOW,
            verified=True,
            reference="record://1",
        )


def test_measurement_window_must_not_end_after_observation_time() -> None:
    with pytest.raises(ValueError, match="after observed_at"):
        DemandObservation(
            product_identity_key="product-1",
            source_id="source",
            source_record_id="record",
            market_code="DE",
            metric="units_sold",
            value=Decimal("1"),
            unit="units",
            observed_at=NOW,
            window_start=WINDOW_START,
            window_end=NOW + timedelta(minutes=1),
            verified=True,
            reference="record://1",
        )


def test_assessment_requires_timezone_aware_now() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        assess_demand((), "product-1", "DE", DemandPolicy(), datetime(2026, 11, 17))
