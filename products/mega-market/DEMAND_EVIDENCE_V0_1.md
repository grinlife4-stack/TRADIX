# Mega Market Demand Evidence v0.3

## Metric classes

### Direct sales observations
- transaction_count
- units_sold

Only these metrics can pass the commercial decision gate, and only when the observation is fresh, positive, verified, tied to an approved source, and backed by a complete report with a retained provenance reference and raw-payload SHA-256.

### Discovery-only proxy observations
- bestseller_rank
- search_interest_index
- review_count
- stockout_rate

These may help discover and prioritize products for investigation. They are not sales counts and cannot pass the commercial decision gate.

### Estimates
- estimated_units_sold
- estimated_revenue
- advertising_attributed_sales_estimate

These remain estimates even when their provenance is genuine. They cannot pass the commercial decision gate.

## Provenance requirements

A verified observation must include:
- a source permission reference matching an approved source;
- a reference to the exact report record;
- SHA-256 of the raw imported payload;
- complete report coverage attested by the source;
- a timezone-aware report period and generation timestamp.

The normalized sales-report importer computes the SHA-256 itself and rejects unapproved sources, mismatched permission references, malformed data, duplicate record IDs, unsupported metrics, numeric JSON values, and invalid time windows.

A hash proves that the imported payload has not changed since hashing. It does not prove that the source's claims are truthful. Permission review and source trust remain separate controls.

## Limits

One positive direct-sales observation permits only a bounded manual-pilot review. The prototype does not yet enforce market/category-specific minimum units, observation-window duration, source coverage beyond the report attestation, refunds/cancellations treatment, or seasonality. These must be calibrated before scale or automation.
