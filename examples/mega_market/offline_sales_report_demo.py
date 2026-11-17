"""Run a fully synthetic, offline Mega Market sales-import decision demo.

This fixture is intentionally not evidence of real demand, source permission,
supplier authorization, or legal compliance.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

from mega_market import (
    Candidate,
    CandidatePolicy,
    DemandPolicy,
    DemandObservation,
    Evidence,
    Money,
    SourceDescriptor,
    UnitEconomicsInput,
    assess_demand,
    evaluate_candidate,
    import_normalized_sales_report,
)


def money(value: str) -> Money:
    return Money(Decimal(value), "EUR")


def main() -> int:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    generated_at = now.isoformat().replace("+00:00", "Z")
    period_start = (now - timedelta(days=14)).isoformat().replace("+00:00", "Z")
    period_end = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")

    # Synthetic descriptor: "approved" here only exercises the import contract.
    # It is not a real permission, license, contract, or source attestation.
    descriptor = SourceDescriptor(
        source_id="demo-sales-source",
        display_name="Synthetic offline fixture",
        access_mode="manual_import",
        permission_status="approved",
        permission_reference="demo://NOT-A-REAL-PERMISSION",
        terms_reviewed_at=now,
    )

    report = {
        "schema_version": "1",
        "report_id": "synthetic-report-001",
        "source_id": descriptor.source_id,
        "permission_reference": descriptor.permission_reference,
        "market_code": "DE",
        "generated_at": generated_at,
        "period_start": period_start,
        "period_end": period_end,
        "coverage_complete": True,
        "records": [
            {
                "record_id": "synthetic-units-001",
                "product_identity_key": "demo:product-001",
                "metric": "units_sold",
                "value": "18",
                "unit": "units",
            },
            {
                "record_id": "synthetic-transactions-001",
                "product_identity_key": "demo:product-001",
                "metric": "transaction_count",
                "value": "12",
                "unit": "transactions",
            },
        ],
    }
    payload = json.dumps(report, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    imported = import_normalized_sales_report(payload, descriptor)

    demand = assess_demand(
        imported.observations,
        product_identity_key="demo:product-001",
        market_code="DE",
        policy=DemandPolicy(max_age=timedelta(days=30)),
        now=now,
    )

    # All evidence below is synthetic. It exists only to exercise the gate.
    evidence = tuple(
        Evidence(
            evidence_type=evidence_type,
            source_id="synthetic-fixture",
            observed_at=now - timedelta(minutes=5),
            verified=True,
            reference=f"demo://synthetic-evidence/{evidence_type}",
        )
        for evidence_type in (
            "demand_signal",
            "market_price",
            "supplier_offer",
            "shipping_quote",
            "direct_fulfillment_authorization",
            "compliance_review",
        )
    )

    economics = UnitEconomicsInput(
        selling_price=money("100.00"),
        supplier_cost=money("40.00"),
        shipping_cost=money("10.00"),
        marketplace_fee=money("10.00"),
        payment_fee=money("3.00"),
        advertising_cost=money("12.00"),
        tax_cost=money("5.00"),
        returns_reserve=money("5.00"),
    )
    decision = evaluate_candidate(
        Candidate(
            candidate_id="synthetic-candidate-001",
            economics=economics,
            evidence=evidence,
            demand_assessment=demand,
        ),
        CandidatePolicy(),
        now,
    )

    result = {
        "mode": "offline_synthetic_demo",
        "network_access": False,
        "source_permission_is_real": False,
        "supplier_authorization_is_real": False,
        "compliance_review_is_real": False,
        "imported_observation_count": len(imported.observations),
        "payload_sha256": imported.raw_payload_sha256,
        "demand_status": demand.status,
        "direct_sales_metrics": list(demand.direct_sales_metrics),
        "unit_economics": {
            "currency": decision.economics.net_profit.currency,
            "total_cost": str(decision.economics.total_cost.amount),
            "net_profit": str(decision.economics.net_profit.amount),
            "net_margin": str(decision.economics.net_margin),
        },
        "decision_status": decision.status,
        "decision_reasons": list(decision.reasons),
        "warning": (
            "Synthetic fixture only. eligible_for_manual_pilot is a simulated "
            "analysis result, not an authorization to buy, list, sell, pay, or scale."
        ),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if decision.status == "eligible_for_manual_pilot" else 1


if __name__ == "__main__":
    raise SystemExit(main())
