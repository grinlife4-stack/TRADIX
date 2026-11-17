# Eurostat public trade-data sample

This is a live-data demonstration of the MegaMarket ingestion and evidence path. It is separate from the synthetic sales-report example.

## Query

- Source: Eurostat Comext
- Dataset: DS-045409, EU trade since 1988 by HS2-4-6 and CN8
- Reporter: Germany (DE)
- Partner: France (FR)
- Product: HS 1001, wheat and meslin
- Flow: imports
- Frequency: annual
- Indicator: value in euros
- Years: 2020–2025

This is a technical sample only. It does not select MegaMarket's eventual launch country or product category.

## Run

From the repository root:

    python examples/mega_market/eurostat_public_trade_demo.py

Optional year range and output directory:

    python examples/mega_market/eurostat_public_trade_demo.py --start-year 2020 --end-year 2025 --output-dir artifacts/megamarket-eurostat

No API key, account, paid package, marketplace login, supplier account, payment method, or wallet is required.

## Files produced

- raw_eurostat_comext_sdmx.csv: exact response bytes from the source.
- normalized_trade_observations.json: validated observations and query dimensions.
- manifest.json: source, retrieval time, raw hash, attribution, reuse review, and limits.
- report.md: readable sample report.

The raw response is hashed with SHA-256 before normalization. The parser rejects unexpected dimensions, duplicate years, malformed values, and empty numeric results.

## Reuse conditions

Eurostat generally permits commercial and non-commercial reuse of its statistical data with source acknowledgement, subject to exceptions. This sample deliberately uses Germany as reporter and France as partner, both EU Member States, and HS level 4. The policy must be checked again for each future query. In particular, do not assume commercial reuse is allowed for every non-EU partner, EFTA-declared trade series, or restricted CN8 series.

Policy: https://ec.europa.eu/eurostat/help/copyright-notice

Attribution is included in the generated manifest and report. Any transformation is disclosed.

## Interpretation boundary

These are official customs trade-flow statistics. They are not retail store sales, consumer sell-through, a current retail price, supplier stock, shipping cost, or profit. They are proxy context only and cannot satisfy the direct-sales evidence required by MegaMarket's commercial decision gate.

The demo does not connect a store or supplier and cannot publish listings, create orders, make purchases, accept payments, convert currency, or transfer BTC.
