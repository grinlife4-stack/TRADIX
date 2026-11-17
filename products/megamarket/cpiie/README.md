# MegaMarket CPIIE read-only core

This provider-neutral engine is isolated under `products/megamarket/cpiie`; it is not part of the generic TRADIX core.

## Implemented

- Register company-specific source metadata using HTTPS URLs.
- Fetch one registered URL only after its exact hostname is explicitly allowlisted.
- Reject IP-literal/local source URLs, non-public DNS answers, cross-host or cross-port redirects, unsupported content types, invalid text encodings, empty responses, and documents over the configured byte limit.
- Pin HTTPS connections to a validated public DNS address to reduce DNS-rebinding and SSRF risk.
- Record immutable document snapshots with SHA-256 hashes and per-source versions.
- Discover candidate policy links from one caller-supplied HTML page. Discovery is bounded, same-origin only, and only proposes candidates; it does not fetch or register them.
- Suggest candidate roles such as terms, affiliate terms, API docs, feed specs, brand guidelines, privacy, disclosure, country restrictions, and support.
- Poll registered sources on demand and persist success/failure history, content hash, version, and change status. Monitor history is append-only at the SQLite layer, constrained against malformed status records, and included in the audit snapshot.
- Validate redirect ports and HTTP framing metadata; reject negative, conflicting, or oversized Content-Length values and normalize incomplete HTTP responses as fetch failures.
- Record evidence locators and excerpts tied to an exact document snapshot.
- Propose policy rules. Every new rule starts as `NEEDS_REVIEW`.
- Require an explicit human reviewer to mark a rule `VERIFIED`, `CONFLICT`, or `EXPIRED`.
- Fail closed when policy is absent, unreviewed, conflicting, expired, or older than a caller-configured freshness limit.
- Export a deterministic audit snapshot without exporting full document bodies.

## Bounded discovery example

```python
from products.megamarket.cpiie.discovery import discover_candidates

candidates = discover_candidates(
    html_from_an_already_approved_page,
    "https://official.example.org/partners",
    max_candidates=50,
)
for candidate in candidates:
    print(candidate.url, candidate.suggested_roles, candidate.matched_terms)
```

Discovery does not establish that a candidate is official, legally usable, or approved. A human/operator must verify the domain and source role, then explicitly register it. Only same-origin links from the supplied page are considered; there is no recursive crawling, sitemap traversal, or external link following.

## On-demand monitoring example

```python
from products.megamarket.cpiie import CPIIERegistry
from products.megamarket.cpiie.fetch import OfficialSourceFetcher
from products.megamarket.cpiie.monitor import PolicyMonitor

registry = CPIIERegistry("megamarket-policy.sqlite3")
fetcher = OfficialSourceFetcher(registry)
monitor = PolicyMonitor(registry, fetcher)

results = monitor.check_all(allowed_hosts={"official.example.org"})
for result in results:
    print(result.source_id, result.status, result.version, result.changed)

history = monitor.history("company-a-affiliate-terms", limit=20)
```

Monitoring is explicit and on-demand. This code does not create a background scheduler or silently poll company websites. A caller must choose the timing and provide the allowlist. Failed checks are recorded and do not replace the last successful document snapshot. A changed hash creates a new immutable document version; unchanged content reuses the existing version. Monitor history cannot be updated or deleted through SQLite, and malformed success/failure records are rejected. Audit exports include monitor history when monitoring has been initialized. Each check first commits a `STARTED` event before network access, then appends a `SUCCESS` or `FAILED` terminal event. If the process or database fails between those steps, history exposes the check as `PENDING`; after confirming no worker is still running, an operator can call `monitor.recover_pending()` to append an `INTERRUPTED` failure receipt without editing prior events. Existing pre-migration monitor tables are rebuilt transactionally into the constrained schema, and legacy rows are preserved.

## Source identity and review audit

A registered `source_id` has an immutable identity tuple: company, role, and canonical URL. Re-registering the same ID with a different company, role, or URL is rejected; register a new ID for a different source. The display title may be refreshed without changing source identity.

Every human review decision is recorded in `rule_review_history` with the prior state, decision, reviewer, and timestamp. History is append-only at the SQLite layer, exposed through `get_review_history(rule_id)`, and included in the deterministic audit snapshot. A failed review transaction rolls back both the rule update and its history entry.

## Policy review boundary

A fetched document is evidence, not permission. Candidate role suggestions are not legal interpretations. New rules remain `NEEDS_REVIEW`; only an identified human reviewer can mark a rule verified. The engine does not infer that an API is enabled, an affiliate application is accepted, or commercial content rights exist.

## Explicitly not implemented

- No recursive crawling, sitemap discovery, scheduled background polling, or automatic source registration.
- No PDF parsing, LLM extraction, automatic rule verification, or legal interpretation.
- No company-specific adapters, credentials, OAuth, affiliate links, account access, forms, emails, support tickets, or API mutations.
- No retailer, affiliate program, country, or category is selected or assumed.

## Run tests

From the repository root:

```bash
python -m pytest -q
```

The implementation uses only the Python standard library and supports Python 3.11+.
