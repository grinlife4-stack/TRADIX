# Multi-Market Dropshipping Platform

Independent product built by TRADIX. This product is not TRADIX itself.

## Purpose
A multi-marketplace product discovery and compliant dropshipping operations platform. It discovers product candidates from authorized marketplace/supplier integrations, evaluates demand and unit economics, verifies that the specific supplier and fulfillment route supports direct-to-customer fulfillment, and only then makes a product eligible for listing.

## Non-goals
- No fabricated catalog, supplier, sales, reviews, orders, or profit figures.
- No scraping, credential sharing, CAPTCHA bypass, or marketplace policy evasion.
- No automatic purchases, customer charges, listings, or payouts until the relevant integration, legal basis, and operator approval are configured.
- A marketplace listing or retail purchase is not automatically a valid dropshipping supply agreement.

## Current foundation
- Responsive, installable-style web dashboard shell with an empty catalog.
- Product eligibility policy and transparent scoring.
- Provider adapter contract; providers are disabled until authorized credentials and documented API scopes exist.
- No live marketplace integrations or real transactions are claimed in v0.1.

## Product eligibility
A candidate is blocked unless it has:
1. Authorized source data with provenance and freshness.
2. Evidence of demand (not merely a popularity label).
3. Verified supplier authorization / wholesale agreement for the intended sales channel.
4. Explicit direct-to-customer fulfillment capability and shipping/returns terms.
5. Positive contribution margin after product cost, fees, shipping, tax estimate, refunds/returns reserve, FX and acquisition cost.
6. No unresolved policy, safety, IP, sanctions, or restricted-category flags.

## Architecture
- `domain/`: provider-neutral product, offer, evidence and eligibility contracts.
- `adapters/`: marketplace and supplier connectors. Each adapter is independently replaceable.
- `web/`: operator dashboard.
- `docs/`: threat model, data contract and rollout gates.

## Run locally
Serve `web/` with any static HTTP server. The dashboard has no backend dependency yet and intentionally shows an empty catalog until a verified provider is connected.

## Release gates
Do not enable live listings or order automation until provider terms/API access, seller-of-record obligations, customer returns, consumer protection, tax, privacy, payment, and supplier agreements have been reviewed for the target market.
