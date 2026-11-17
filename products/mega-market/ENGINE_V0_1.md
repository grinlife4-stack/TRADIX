# Mega Market Analysis Core v0.3

## Purpose

This is a deterministic, side-effect-free analysis core. It does not crawl websites, call marketplace APIs, contact suppliers, publish listings, place orders, accept payments, exchange currencies, or transfer crypto-assets.

## Implemented

- Per-unit economics using Python Decimal only.
- Evidence provenance and freshness checks.
- Permission-backed normalized sales-report import.
- SHA-256 integrity hash for the exact imported report payload.
- Strict schema, duplicate-key, duplicate-record, timestamp, market, metric, unit, and decimal validation.
- Incomplete-coverage reports remain unverified and cannot pass the candidate gate.
- Candidate qualification requires fresh, verified, positive direct-sales observations.
- Rank, search, reviews, stockout signals, and estimates remain discovery-only.

## Sales report trust boundary

The importer accepts normalized JSON only. A source must be marked approved and the report's permission reference must match the registered source descriptor. Each accepted observation retains the report reference, permission reference, payload hash, report period, and coverage status.

The SHA-256 hash proves payload integrity after import; it does not prove that the source's business claims are true. Source authorization and the source's attestation of complete report coverage must be independently reviewed. A manual-import permission is an operator attestation, not an automatic legal determination.

## Decision semantics

A candidate can become eligible for a bounded manual pilot only when configured unit-economics and other evidence gates pass and at least one fresh, verified, positive direct-sales observation exists.

This is not a purchase authorization, forecast, or authorization to scale. Market/category-specific minimum units, period length, source coverage, refunds/cancellations, and seasonality thresholds remain to be defined before scaling or automated operation.

## Safety boundary

No live connector, scraping, order, listing, payment, FX, or crypto operation is included. No secrets are stored. The package remains side-effect free.
