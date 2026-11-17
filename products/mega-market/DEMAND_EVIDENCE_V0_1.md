# Mega Market Demand Evidence v0.2

## Purpose

Represent demand-related observations without collapsing incomparable metrics into a synthetic score or presenting estimates as actual sales.

## Metric classes

### Direct sales observations
- transaction_count
- units_sold

These are the only metric classes accepted by the commercial decision gate. To pass the current prototype's manual-pilot gate, at least one observation must be fresh, verified, positive, and have a provenance reference. A zero-only record does not qualify.

### Discovery-only proxy observations
- bestseller_rank
- search_interest_index
- review_count
- stockout_rate

These can help discover and prioritize products for investigation. They are not direct unit-sales counts and cannot pass the commercial decision gate.

### Estimates
- estimated_units_sold
- estimated_revenue
- advertising_attributed_sales_estimate

These remain estimates even when the source record is verified as a genuine estimate. Verification confirms provenance, not that the estimate equals actual sales. Estimates cannot pass the commercial decision gate.

## Implemented controls

- Product and market scoping.
- Decimal-only non-negative metric values.
- Explicit units and measurement windows.
- Timezone-aware observation and measurement timestamps.
- Future, stale, and unverified evidence is excluded from usable observations and reported separately.
- Verified observations require a provenance reference.
- Classification into direct sales observations, proxy observations, estimates only, or insufficient evidence.
- Original metric observations are preserved individually. No cross-metric addition, universal demand score, or sales-volume inference is performed.

## Interpretation and limits

A positive direct-sales observation establishes only that a source reports sales in a stated period. It does not prove that the same sales volume will repeat.

The current prototype does not yet enforce a market/category-specific minimum number of units, observation-window duration, source coverage, treatment of cancellations/refunds, or seasonality. These requirements must be set and validated for the chosen marketplace and category before scaling or automated purchasing/listing.

The assessment is an evidence classification, not a forecast or an authorization to buy, list, or stock a product.
