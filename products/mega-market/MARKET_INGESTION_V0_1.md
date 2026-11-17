# Mega Market Market-Data Ingestion v0.1

## Purpose

Provide a source-neutral boundary for importing product listing observations from approved market-data sources. This layer does not scrape websites, bypass access controls, infer sales from rank, or contact a source unless a separately implemented adapter has documented permission.

## Implemented

- Adapter protocol with a stable source identity and a listing-fetch method.
- Source registry that refuses pending or blocked sources.
- Permission metadata requiring a reference and timezone-aware terms-review timestamp before a source can be registered as approved.
- Market-specific collection requests using two-letter uppercase market codes.
- Per-source result limits and validation that source identity and market identity match the request.
- Partial-failure reporting. One failed source does not silently invalidate or hide successful results from other sources.
- Duplicate source-record suppression.
- Conservative cross-source identity matching:
  1. Validated GTIN with checksum.
  2. Exact normalized brand plus manufacturer part number.
  3. Exact normalized brand, title, and variant.
  4. Otherwise, source-scoped record identity only.
- Stable deterministic grouping that preserves every source observation and its original price currency.

## Deliberate non-features

- No live adapters, web crawling, browser automation, or marketplace login.
- No fuzzy title matching or AI-generated identity decisions.
- No currency conversion or price comparison across currencies.
- No demand score, sales-volume estimate, or bestseller-rank-to-sales conversion.
- No database writes, order placement, listing publication, payment, or settlement.

## Why matching is conservative

Incorrectly merging two different products can corrupt supplier selection, margin calculations, stock checks, and customer fulfillment. A false split can be reviewed and merged later; a false merge can silently contaminate every downstream decision. Weak identifiers therefore remain source-scoped.

GTINs are accepted only after length and check-digit validation. Invalid GTIN values are not used as identity keys.

## Source authorization

A source may be registered only when its permission status is approved and both a permission reference and terms-review timestamp are present. This is a local admission control, not a legal determination. The reference must point to the actual applicable API terms, license, agreement, or documented manual-import authorization.

## Next required layer

The next layer should add metric-specific demand observations, with explicit separation between observed transactions, platform ranking, search interest, review velocity, stockout observations, advertising estimates, and model estimates. These metrics must not be summed into a single demand number without a validated calibration dataset.

Live source adapters should be selected only after target market, country, source terms, and available credentials or public endpoints are established.
