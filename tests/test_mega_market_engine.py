from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from mega_market import (
    Candidate,
    CandidatePolicy,
    Evidence,
    EvidencePolicy,
    Money,
    UnitEconomicsInput,
    assess_evidence,
    calculate_unit_economics,
    evaluate_candidate,
)


def money(value: str, currency: str = "EUR") -> Money:
    return Money(Decimal(value), currency)


def economics(
    *,
    selling_price: str = "100.00",
    supplier_cost: str = "40.00",
    shipping_cost: str = "10.00",
    marketplace_fee: str = "10.00",
    payment_fee: str = "3.00",
    advertising_cost: str = "12.00",
    tax_cost: str = "5.00",
    returns_reserve: str = "5.00",
) -> UnitEconomicsInput:
    return UnitEconomicsInput(
        selling_price=money(selling_price),
        supplier_cost=money(supplier_cost),
        shipping_cost=money(shipping_cost),
        marketplace_fee=money(marketplace_fee),
        payment_fee=money(payment_fee),
        advertising_cost=money(advertising_cost),
        tax_cost=money(tax_cost),
        returns_reserve=money(returns_reserve),
    )


def complete_evidence(now: datetime) -> tuple[Evidence, ...]:
    required = EvidencePolicy().required_types
    return tuple(
        Evidence(
            evidence_type=item,
            source_id=f"test-source-{index}",
            observed_at=now - timedelta(minutes=5),
            verified=True,
            reference=f"fixture://evidence/{item}",
        )
        for index, item in enumerate(required)
    )


def test_unit_economics_calculates_all_variable_costs() -> None:
    result = calculate_unit_economics(economics())
    assert result.total_cost == money("85.00")
    assert result.net_profit == money("15.00")
    assert result.net_margin == Decimal("0.15")


def test_unit_economics_rejects_mixed_currencies() -> None:
    with pytest.raises(ValueError, match="same currency"):
        UnitEconomicsInput(
            selling_price=money("100"),
            supplier_cost=money("40", "USD"),
            shipping_cost=money("10"),
            marketplace_fee=money("10"),
            payment_fee=money("3"),
            advertising_cost=money("12"),
            tax_cost=money("5"),
            returns_reserve=money("5"),
        )


def test_unit_economics_rejects_float_amounts() -> None:
    with pytest.raises(TypeError, match="Decimal"):
        Money(1.1, "EUR")  # type: ignore[arg-type]


def test_unit_economics_rejects_negative_costs() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        economics(supplier_cost="-1")


def test_evidence_gate_requires_all_fresh_verified_types() -> None:
    now = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
    result = assess_evidence(complete_evidence(now), EvidencePolicy(), now)
    assert result.ready is True
    assert result.missing == ()
    assert result.stale == ()
    assert result.unverified == ()


def test_evidence_gate_reports_missing_and_stale_records() -> None:
    now = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
    evidence = (
        Evidence(
            evidence_type="demand_signal",
            source_id="market-api",
            observed_at=now - timedelta(days=3),
            verified=True,
        ),
    )
    result = assess_evidence(evidence, EvidencePolicy(), now)
    assert result.ready is False
    assert "market_price" in result.missing
    assert "demand_signal" in result.stale


def test_evidence_gate_rejects_naive_timestamps() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        Evidence("demand_signal", "source", datetime(2026, 11, 17), True)


def test_candidate_is_held_without_evidence() -> None:
    now = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
    result = evaluate_candidate(Candidate("sku-1", economics()), CandidatePolicy(), now)
    assert result.status == "hold"
    assert "required evidence is missing" in result.reasons


def test_candidate_can_only_become_eligible_for_manual_pilot() -> None:
    now = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
    candidate = Candidate("sku-2", economics(), complete_evidence(now))
    result = evaluate_candidate(candidate, CandidatePolicy(), now)
    assert result.status == "eligible_for_manual_pilot"
    assert result.evidence.ready is True
    assert "manual review" in result.reasons[0]


def test_candidate_is_rejected_when_margin_is_below_policy() -> None:
    now = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
    policy = CandidatePolicy(minimum_net_margin=Decimal("0.20"))
    result = evaluate_candidate(
        Candidate("sku-3", economics(), complete_evidence(now)),
        policy,
        now,
    )
    assert result.status == "reject"
