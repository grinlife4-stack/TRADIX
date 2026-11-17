from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from mega_market.demand import DemandObservation, DemandPolicy, assess_demand

NOW=datetime(2026,11,17,12,0,tzinfo=timezone.utc)
WINDOW_START=NOW-timedelta(hours=1)

def observation(metric="units_sold",value="12",*,product="gtin:04006381333931",market="DE",source="market-a",observed_at=NOW,verified=True,reference="source-record://1"):
    return DemandObservation(
        product_identity_key=product,source_id=source,source_record_id=f"{source}-record",
        market_code=market,metric=metric,  # type: ignore[arg-type]
        value=Decimal(value),unit="units",observed_at=observed_at,
        window_start=observed_at-timedelta(hours=1),window_end=observed_at,
        verified=verified,reference=reference,
        permission_reference="fixture://permissions/market-source" if verified else None,
        raw_payload_sha256="b"*64 if verified else None,
        coverage_complete=verified,
    )

def assess(*items):
    return assess_demand(tuple(items),"gtin:04006381333931","DE",DemandPolicy(),NOW)

def test_direct_sales_observations_are_distinguished_from_proxy_signals():
    result=assess(observation("units_sold","12"),observation("bestseller_rank","34",source="market-b"),observation("search_interest_index","78",source="market-c"))
    assert result.status=="direct_sales_observations_available"
    assert result.direct_sales_metrics==("units_sold",)
    assert result.proxy_metrics==("bestseller_rank","search_interest_index")
    assert len(result.usable_observations)==3

def test_rank_and_search_interest_are_only_proxy_observations():
    result=assess(observation("bestseller_rank","34"),observation("search_interest_index","78",source="market-b"))
    assert result.status=="proxy_observations_only" and result.direct_sales_metrics==()

def test_estimates_never_become_observed_sales():
    result=assess(observation("estimated_units_sold","500"),observation("advertising_attributed_sales_estimate","900",source="market-b"))
    assert result.status=="estimates_only" and result.direct_sales_metrics==() and result.proxy_metrics==()
    assert result.estimate_metrics==("advertising_attributed_sales_estimate","estimated_units_sold")

def test_stale_observations_are_not_usable():
    result=assess(observation("units_sold","12",observed_at=NOW-timedelta(days=3)))
    assert result.status=="insufficient_evidence" and result.stale_metrics==("units_sold",) and result.usable_observations==()

def test_unverified_observations_are_not_usable():
    result=assess(observation("units_sold","12",verified=False,reference=None))
    assert result.status=="insufficient_evidence" and result.unverified_metrics==("units_sold",)

def test_future_observations_are_not_usable():
    result=assess(observation("units_sold","12",observed_at=NOW+timedelta(minutes=5)))
    assert result.status=="insufficient_evidence" and result.future_metrics==("units_sold",)

def test_other_product_and_market_observations_are_ignored():
    result=assess(observation(product="other-product"),observation(market="FR",source="market-b"))
    assert result.status=="insufficient_evidence" and result.ignored_other_product_or_market==2

def test_observation_values_are_not_summed_across_metric_types():
    result=assess(observation("units_sold","12"),observation("bestseller_rank","34",source="market-b"),observation("search_interest_index","78",source="market-c"))
    assert len(result.usable_observations)==3
    assert not hasattr(result,"demand_score") and not hasattr(result,"estimated_monthly_sales")

def test_verified_observation_requires_complete_provenance():
    with pytest.raises(ValueError,match="provenance reference"): observation(reference=None)
    with pytest.raises(ValueError,match="source permission reference"):
        DemandObservation("p","s","r","DE","units_sold",Decimal("1"),"units",NOW,WINDOW_START,NOW,True,"r://1")
    with pytest.raises(ValueError,match="raw payload SHA-256"):
        DemandObservation("p","s","r","DE","units_sold",Decimal("1"),"units",NOW,WINDOW_START,NOW,True,"r://1","permission://1",None,True)
    with pytest.raises(ValueError,match="complete report coverage"):
        DemandObservation("p","s","r","DE","units_sold",Decimal("1"),"units",NOW,WINDOW_START,NOW,True,"r://1","permission://1","c"*64,False)

def test_demand_values_reject_floats():
    with pytest.raises(TypeError,match="Decimal"):
        DemandObservation("product-1","source","record","DE","units_sold",1.5,"units",NOW,WINDOW_START,NOW,True,"record://1")  # type: ignore[arg-type]

def test_measurement_window_must_not_end_after_observation_time():
    with pytest.raises(ValueError,match="after observed_at"):
        DemandObservation("product-1","source","record","DE","units_sold",Decimal("1"),"units",NOW,WINDOW_START,NOW+timedelta(minutes=1),True,"record://1")

def test_assessment_requires_timezone_aware_now():
    with pytest.raises(ValueError,match="timezone-aware"):
        assess_demand((),"product-1","DE",DemandPolicy(),datetime(2026,11,17))
