from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from mega_market import (
    Candidate, CandidatePolicy, DemandObservation, DemandPolicy, Evidence,
    EvidencePolicy, Money, UnitEconomicsInput, assess_demand, assess_evidence,
    calculate_unit_economics, evaluate_candidate,
)

def money(value: str, currency: str = "EUR") -> Money:
    return Money(Decimal(value), currency)

def economics(*, selling_price="100.00", supplier_cost="40.00", shipping_cost="10.00",
              marketplace_fee="10.00", payment_fee="3.00", advertising_cost="12.00",
              tax_cost="5.00", returns_reserve="5.00") -> UnitEconomicsInput:
    return UnitEconomicsInput(
        selling_price=money(selling_price), supplier_cost=money(supplier_cost),
        shipping_cost=money(shipping_cost), marketplace_fee=money(marketplace_fee),
        payment_fee=money(payment_fee), advertising_cost=money(advertising_cost),
        tax_cost=money(tax_cost), returns_reserve=money(returns_reserve),
    )

def complete_evidence(now: datetime) -> tuple[Evidence, ...]:
    return tuple(Evidence(
        evidence_type=item, source_id=f"test-source-{index}",
        observed_at=now-timedelta(minutes=5), verified=True,
        reference=f"fixture://evidence/{item}",
    ) for index, item in enumerate(EvidencePolicy().required_types))

def demand_assessment(now: datetime, metric: str = "bestseller_rank", value: str = "25"):
    observation = DemandObservation(
        product_identity_key="product-1", source_id="market-source",
        source_record_id="record-1", market_code="DE", metric=metric,  # type: ignore[arg-type]
        value=Decimal(value), unit="provider-unit",
        observed_at=now-timedelta(minutes=5), window_start=now-timedelta(hours=1),
        window_end=now-timedelta(minutes=5), verified=True,
        reference="fixture://demand/record-1",
    )
    return assess_demand((observation,), "product-1", "DE", DemandPolicy(), now)

def test_unit_economics_calculates_all_variable_costs():
    result=calculate_unit_economics(economics())
    assert result.total_cost == money("85.00")
    assert result.net_profit == money("15.00")
    assert result.net_margin == Decimal("0.15")

def test_unit_economics_rejects_mixed_currencies():
    with pytest.raises(ValueError, match="same currency"):
        UnitEconomicsInput(
            selling_price=money("100"), supplier_cost=money("40","USD"),
            shipping_cost=money("10"), marketplace_fee=money("10"),
            payment_fee=money("3"), advertising_cost=money("12"),
            tax_cost=money("5"), returns_reserve=money("5"),
        )

def test_unit_economics_rejects_float_amounts():
    with pytest.raises(TypeError, match="Decimal"):
        Money(1.1, "EUR")  # type: ignore[arg-type]

def test_unit_economics_rejects_negative_costs():
    with pytest.raises(ValueError, match="cannot be negative"):
        economics(supplier_cost="-1")

def test_evidence_gate_requires_all_fresh_verified_types():
    now=datetime(2026,11,17,12,0,tzinfo=timezone.utc)
    result=assess_evidence(complete_evidence(now),EvidencePolicy(),now)
    assert result.ready is True and result.missing == () and result.stale == () and result.unverified == ()

def test_evidence_gate_reports_missing_and_stale_records():
    now=datetime(2026,11,17,12,0,tzinfo=timezone.utc)
    evidence=(Evidence("demand_signal","market-api",now-timedelta(days=3),True),)
    result=assess_evidence(evidence,EvidencePolicy(),now)
    assert result.ready is False and "market_price" in result.missing and "demand_signal" in result.stale

def test_evidence_gate_rejects_naive_timestamps():
    with pytest.raises(ValueError,match="timezone-aware"):
        Evidence("demand_signal","source",datetime(2026,11,17),True)

def test_candidate_is_held_without_evidence_or_demand_assessment():
    now=datetime(2026,11,17,12,0,tzinfo=timezone.utc)
    result=evaluate_candidate(Candidate("sku-1",economics()),CandidatePolicy(),now)
    assert result.status=="hold" and "required evidence is missing" in result.reasons

def test_proxy_signals_are_discovery_only_and_cannot_pass_candidate_gate():
    now=datetime(2026,11,17,12,0,tzinfo=timezone.utc)
    candidate=Candidate("sku-2",economics(),complete_evidence(now),demand_assessment(now,"bestseller_rank","25"))
    result=evaluate_candidate(candidate,CandidatePolicy(),now)
    assert result.status=="hold"
    assert result.demand_status=="proxy_observations_only"
    assert "positive direct-sales observations" in result.reasons[0]
    assert "discovery-only" in result.reasons[0]

def test_positive_direct_sales_observation_can_pass_only_to_manual_pilot():
    now=datetime(2026,11,17,12,0,tzinfo=timezone.utc)
    candidate=Candidate("sku-3",economics(),complete_evidence(now),demand_assessment(now,"units_sold","25"))
    result=evaluate_candidate(candidate,CandidatePolicy(),now)
    assert result.status=="eligible_for_manual_pilot"
    assert result.demand_status=="direct_sales_observations_available"
    assert "not authorization to scale" in result.reasons[1]

def test_zero_direct_sales_observation_does_not_pass_candidate_gate():
    now=datetime(2026,11,17,12,0,tzinfo=timezone.utc)
    candidate=Candidate("sku-4",economics(),complete_evidence(now),demand_assessment(now,"units_sold","0"))
    result=evaluate_candidate(candidate,CandidatePolicy(),now)
    assert result.status=="hold" and "positive direct-sales observations" in result.reasons[0]

def test_estimates_only_cannot_pass_candidate_gate():
    now=datetime(2026,11,17,12,0,tzinfo=timezone.utc)
    candidate=Candidate("sku-5",economics(),complete_evidence(now),demand_assessment(now,"estimated_units_sold","500"))
    result=evaluate_candidate(candidate,CandidatePolicy(),now)
    assert result.status=="hold" and "positive direct-sales observations" in result.reasons[0]

def test_stale_demand_assessment_cannot_pass_candidate_gate():
    now=datetime(2026,11,17,12,0,tzinfo=timezone.utc)
    candidate=Candidate("sku-6",economics(),complete_evidence(now),
                        demand_assessment(now-timedelta(hours=2),"units_sold","25"))
    result=evaluate_candidate(candidate,CandidatePolicy(),now)
    assert result.status=="hold" and "demand assessment is stale" in result.reasons[0]

def test_candidate_is_rejected_when_margin_is_below_policy():
    now=datetime(2026,11,17,12,0,tzinfo=timezone.utc)
    policy=CandidatePolicy(minimum_net_margin=Decimal("0.20"))
    result=evaluate_candidate(
        Candidate("sku-7",economics(),complete_evidence(now),demand_assessment(now,"units_sold","25")),
        policy,now,
    )
    assert result.status=="reject"
