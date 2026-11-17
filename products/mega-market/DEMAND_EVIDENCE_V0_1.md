# Mega Market Demand Evidence v0.1

## Purpose

Represent demand-related observations without collapsing incomparable metrics into a synthetic score or presenting estimates as actual sales.

## Metric classes

### Direct sales observations
- transaction_count
- units_sold

These are treated as direct sales observations only when the source record is fresh, verified, and has a provenance reference. Their availability does not establish that the same sales volume will repeat.

### Proxy observations
- bestseller_rank
- search_interest_index
- review_count
- stockout_rate

These can indicate attention, ranking, review activity, or availability pressure. None is a direct unit-sales count. Rank is ordinal and provider/category-specific; search indices are provider-specific; review counts are not equivalent to purchases.

### Estimates
- estimated_units_sold
- estimated_revenue
- advertising_attributed_sales_estimate

These remain estimates even when the source record is verified as a genuine estimate. Verification confirms provenance, not that the estimate equals actual sales.

## Implemented controls

- Product and market scoping.
- Decimal-only non-negative metric values.
- Explicit units and measurement windows.
- Timezone-aware observation and measurement timestamps.
- Future, stale, and unverified evidence is excluded from usable observations and reported separately.
- Verified observations require a provenance reference.
- Classification into direct sales observations, proxy observations, estimates only, or insufficient evidence.
- Original metric observations are preserved individually. No cross-metric addition, universal demand score, or sales-volume inference is performed.

## Interpretation

The status is an evidence classification, not a recommendation to buy, list, or stock a product. Even direct sales observations require market context, period comparability, refunds/cancellations treatment, and source coverage analysis before forecasting.

A later forecasting model must be trained and validated against actual outcomes for the target market and category. It must publish calibration error and confidence intervals and must not silently promote estimates to observed facts.
