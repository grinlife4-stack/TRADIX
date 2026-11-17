# Product selection and automation policy

## Ranking
Rank candidates only from timestamped, provenance-bearing evidence. Separate observed facts from estimates. Missing values score zero and lower confidence. Never describe rank or popularity as verified unit sales unless the source explicitly provides that fact.

## Hard eligibility gates
A high score cannot override any blocker:
- authorized and fresh source data;
- credible demand evidence;
- supplier identity and written wholesale resale authorization for the channel;
- explicit direct fulfillment capability;
- shipping, tracking, returns and packaging terms;
- positive contribution margin under conservative assumptions;
- category, intellectual-property, safety, sanctions and marketplace policy review.

## Financial model
Contribution margin must include selling price less supplier cost, marketplace/payment fees, shipping, duties/tax estimates, FX costs, refund/return reserve, chargebacks and acquisition cost. Display currency and quote timestamp. Do not use gross spread as profit.

## Automation stages
DISCOVER -> VERIFY -> SCORE -> HUMAN_APPROVE -> LIST -> ORDER -> TRACK -> RECONCILE.
v0.1 supports only the foundation for DISCOVER/VERIFY/SCORE. Listing, ordering, payment and payout are disabled.

## Failure behavior
Unknown, stale, contradictory or unauthorized evidence blocks eligibility. Provider failure must never silently fall back to fabricated or stale values.
