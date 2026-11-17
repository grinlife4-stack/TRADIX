# Mega Market Analysis Core v0.1

## Purpose

This is the first executable vertical slice of Mega Market. It is a local, deterministic analysis core. It does not crawl websites, call marketplace APIs, contact suppliers, publish listings, place orders, accept payments, exchange currencies, or transfer crypto-assets.

## Implemented

- Per-unit economics using Python `Decimal`, with no implicit float conversion or currency conversion.
- Explicit inputs for selling price, supplier cost, shipping, marketplace fee, payment fee, advertising, tax, and a returns reserve.
- Currency consistency validation. Mixed-currency inputs fail closed and must be converted by a separately audited FX adapter before calculation.
- Evidence provenance and freshness checks.
- Required evidence categories: demand signal, market price, supplier offer, shipping quote, direct-fulfillment authorization, and compliance review.
- Candidate outcomes: `hold`, `reject`, or `eligible_for_manual_pilot`.
- A candidate can never trigger a live operation through this package.

## Decision semantics

`eligible_for_manual_pilot` means only that the supplied unit economics meet the configured threshold and every required evidence category has at least one fresh, verified record. It is not a purchase authorization, supplier approval, legal opinion, or proof that demand estimates are accurate.

Default evidence freshness is 24 hours. The policy is configurable. Evidence timestamps must be timezone-aware. Unverified, stale, missing, or future-dated evidence prevents eligibility.

## Financial semantics

All amounts are per unit and must use one ISO-style three-letter uppercase currency code. Cost fields are absolute monetary amounts, not percentages. Fee and tax adapters must calculate those amounts from their own documented rules before passing them to this core. No tax rate, exchange rate, shipping cost, sales volume, or market demand is invented here.

Net profit = selling price - (supplier cost + shipping + marketplace fee + payment fee + advertising + tax + returns reserve).

Net margin = net profit / selling price.

The calculation does not silently round. Currency-specific rounding belongs at a later settlement boundary, not in the analysis core.

## Not implemented yet

- Market/source connectors and API permission registry.
- Product identity matching and deduplication.
- Demand estimation and confidence calibration.
- Supplier discovery, contract verification, and service-level monitoring.
- Country-specific tax, consumer-protection, customs, and product-compliance rules.
- FX conversion adapter and provenance.
- Storefront, listing, inventory, order, customer-service, payment, and settlement adapters.
- Persistent product/event history or operator UI.

## Safety boundary

This package is side-effect free. It performs calculations and evidence assessment only. Any future connector that can publish, order, pay, refund, or transfer value must be a separate adapter behind explicit policy, bounded permissions, audit records, and a kill switch. No secrets belong in this package or in the repository.
