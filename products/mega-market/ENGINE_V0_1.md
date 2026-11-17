# Mega Market Analysis Core v0.2

## Purpose

This is a deterministic, side-effect-free analysis core. It does not crawl websites, call marketplace APIs, contact suppliers, publish listings, place orders, accept payments, exchange currencies, or transfer crypto-assets.

## Implemented

- Per-unit economics using Python Decimal only.
- Explicit inputs for selling price, supplier cost, shipping, marketplace fee, payment fee, advertising, tax, and a returns reserve.
- Currency consistency validation. Mixed-currency inputs fail closed and must be converted by a separately audited FX adapter before calculation.
- Evidence provenance and freshness checks.
- Required evidence categories: market price, supplier offer, shipping quote, direct-fulfillment authorization, and compliance review, plus structured demand evidence.
- Candidate outcomes: hold, reject, or eligible for manual pilot.
- A candidate cannot trigger a live operation through this package.

## Demand evidence and decision gate

Demand signals have two distinct jobs:

1. Discovery: rank, search interest, reviews, stockout rate, and third-party sales estimates may help find products worth investigating. They do not establish actual sales.
2. Commercial qualification: only fresh, verified, positive direct-sales observations (transaction_count or units_sold) can pass the demand gate for a bounded manual pilot.

Proxy metrics and estimates are never substitutes for sales records. Missing, zero-only, stale, unverified, or future-dated direct-sales evidence leaves the candidate on hold.

A positive sales observation is not proof that the volume will repeat. The current prototype does not yet enforce market-specific minimum units, observation-window length, source coverage, refunds/cancellations treatment, or seasonality. Those thresholds must be defined and validated for the chosen marketplace and category before any scaled or automated operation.

## Decision semantics

eligible_for_manual_pilot means only that:
- configured unit-economics thresholds are met;
- all required market, supplier, shipping, fulfillment, and compliance evidence is fresh and verified;
- at least one fresh, verified, positive direct-sales observation is present.

It is not a purchase authorization, supplier approval, legal opinion, forecast, or authorization to scale. Human review and separate operational approval remain mandatory.

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
