# Normalized Sales Report Import v0.1

## Purpose

Define a source-neutral, offline import format for direct-sales reports. This is not a live marketplace connector and does not scrape or retrieve sales data.

## Source admission

The importing source must have a SourceDescriptor with permission_status=approved, a permission reference, and a reviewed terms timestamp. The report's source_id and permission_reference must exactly match that descriptor.

Manual-import permission is an operator attestation that the file was obtained lawfully. The importer cannot independently decide whether a contract, API license, or source claim is legally sufficient.

## Payload schema

UTF-8 JSON, maximum 10 MB, maximum 10,000 records. Schema version is the string "1". Duplicate JSON keys and duplicate record IDs are rejected. Monetary or quantity values must be decimal strings, never JSON floating-point numbers.

Required root fields:
- schema_version
- report_id
- source_id
- permission_reference
- market_code
- generated_at
- period_start
- period_end
- coverage_complete
- records

Each record requires:
- record_id
- product_identity_key
- metric: transaction_count or units_sold only
- value: non-negative decimal string
- unit: transactions or units, matching the metric

All timestamps must include a timezone. The report period must be ordered and cannot end after generated_at.

## Verification and audit

The importer computes SHA-256 over the exact raw payload bytes and attaches the digest, permission reference, report reference, period, and coverage status to each observation.

Only a report marked coverage_complete=true from an approved source creates verified observations. Incomplete reports can be imported for review but cannot pass the decision gate.

SHA-256 provides payload integrity after import. It does not authenticate the source or prove that its sales claims are true. Source trust, permission, and coverage attestation remain separate review obligations.

## Not included

- Live APIs, scraping, login, credentials, or scheduled downloads.
- Currency conversion or financial settlement.
- Inferring sales from rankings, reviews, stockouts, search interest, or model estimates.
- Automatic purchase, listing, or payment.
