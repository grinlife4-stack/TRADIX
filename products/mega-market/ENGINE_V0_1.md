# Mega Market Analysis Core v0.1

## Purpose

This is the first executable, deterministic analysis core. It is side-effect free. It does not crawl websites, call marketplace APIs, contact suppliers, publish listings, place orders, accept payments, exchange currencies, or transfer crypto-assets.

## Implemented

- Per-unit economics using Python Decimal only.
- Explicit inputs for selling price, supplier cost, shipping, marketplace fee, payment fee, advertising, tax, and a returns reserve.
- Currency consistency validation. Mixed-currency inputs fail closed and must be converted by a separately audited FX adapter before calculation.
- Evidence provenance and freshness checks.
- Required evidence categories: market price, supplier offer, shipping quote, direct-fulfillment authorization, and compliance review, plus the structured demand assessment.
- Candidate outcomes: hold, reject, or eligible for manual pilot.
- A candidate cannot trigger a live operation through this package.

## Demand gate

The candidate decision core consumes the structured demand assessment. By default, either fresh verified direct-sales observations or fresh verified proxy observations can qualify a candidate for a bounded manual pilot. A stricter policy can require direct sales observations only.

Estimates alone, missing observations, stale assessments, and future-dated assessments fail closed. A proxy-only result is not evidence of sales volume; it can only support a small manual validation pilot. The decision output states this limitation.

## Decision semantics

Eligible for manual pilot means only that:
- configured unit-economics thresholds are met;
- all required market, supplier, shipping, fulfillment, and compliance evidence is fresh and verified;
- the structured demand assessment is fresh and contains verified observed metrics.

It is not a purchase authorization, supplier approval, legal opinion, or proof that demand estimates are accurate. Human review and separate operational approval remain mandatory.

## Financial semantics

All amounts are per unit and must use one ISO-style three-letter uppercase currency code. Cost fields are absolute monetary amounts, not percentages. Fee and tax adapters must calculate those amounts from their own documented rules before passing them to this core. No tax rate, exchange rate, shipping cost, sales volume, or market demand is invented here.

Net profit = selling price - (supplier cost + shipping + marketplace fee + payment fee + advertising + tax + returns reserve).

Net margin = net profit / selling price.

The calculation does not silently round. Currency-specific rounding belongs at a later settlement boundary, not in the analysis core.

## Not implemented yet

- Live market/source connectors and API permission registry persistence.
- Product identity matching and deduplication beyond conservative exact identifiers.
- Demand forecasting, calibrated probabilities, and confidence intervals.
- Supplier discovery, contract verification, and service-level monitoring.
- Country-specific tax, consumer-protection, customs, and product-compliance rules.
- FX conversion adapter and provenance.
- Storefront, listing, inventory, order, customer-service, payment, and settlement adapters.
- Persistent product/event history or operator UI.

## Safety boundary

This package is side-effect free. It performs calculations and evidence assessment only. Any future connector that can publish, order, pay, refund, or transfer value must be a separate adapter behind explicit policy, bounded permissions, audit records, and a kill switch. No secrets belong in this package or in the repository.
