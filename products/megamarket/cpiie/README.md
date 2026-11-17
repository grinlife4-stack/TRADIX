# MegaMarket CPIIE read-only core

This is the first executable slice of the Company Policy Intelligence & Interaction Engine. It is deliberately isolated under `products/megamarket/cpiie`; it is not part of the generic TRADIX core.

## Implemented

- Register a company-specific official source using an HTTPS URL.
- Record manually supplied document snapshots with deterministic SHA-256 hashes and per-source versions.
- Record evidence locators and excerpts tied to an exact document snapshot.
- Propose policy rules. Every new rule starts as `NEEDS_REVIEW`.
- Permit explicit human review to mark a rule `VERIFIED`, `CONFLICT`, or `EXPIRED`.
- Evaluate a capability fail-closed when policy is absent, unreviewed, conflicting, or expired.
- Export a deterministic audit snapshot.

## Explicitly not implemented

- No network fetching, crawling, scraping, or scheduled monitoring.
- No LLM extraction or automatic verification.
- No company adapters, credentials, OAuth, affiliate links, or account access.
- No forms, emails, support tickets, API calls, or other external interaction.
- No retailer, affiliate-program, country, or category is selected or assumed.

Document content must currently be supplied by a trusted caller after obtaining it through an authorized route. This registry records provenance; it does not itself prove that a source is legally authoritative or that a company granted permission.

## Run tests

From the repository root:

```bash
python -m unittest discover -s tests/megamarket_cpiie -v
```

The module uses only the Python standard library and supports Python 3.11+.
