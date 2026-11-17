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
- Require every evidence excerpt to occur verbatim in the exact cited document snapshot.
- Enforce document-snapshot, evidence-record, and rule-content immutability with SQLite triggers; source identity is also protected and source records cannot be deleted.
- Append rule-review history from a database trigger in the same transaction as the review-state change, including direct SQL state changes that satisfy the review guard.
- Require timezone-aware ISO-8601 timestamps for document fetch times and rule expiry; compare parsed UTC instants rather than timestamp strings.
- Propose policy rules. Every new rule starts as `NEEDS_REVIEW`.
- Require each rule to declare a structured `ALLOW` or `DENY` effect before it can contribute to a positive capability decision. Omitted effects remain `UNSPECIFIED` and block evaluation, including rules migrated from older databases.
- Apply deny-overrides semantics: any current, verified `DENY` rule blocks the capability even if another rule says `ALLOW`; unknown effect values fail closed.
- Require a signed reviewer assertion validated by an injected trusted identity-provider adapter before any rule review (`VERIFIED`, `CONFLICT`, or `EXPIRED`).
- Enforce exact company, capability, and decision scope; persist the issuer, subject, key ID, assertion ID, authentication window, and signed authorization receipt with each review.
- Re-verify the signed authorization receipt during every capability evaluation; missing, invalid, expired, or revoked receipts fail closed.
- Reject direct SQL review-state updates that do not include a complete authenticated reviewer receipt; legacy reviewer labels migrate without authority.
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

Every human review decision is recorded in `rule_review_history` with the prior state, decision, reviewer, and timestamp. History is append-only at the SQLite layer, exposed through `get_review_history(rule_id)`, and included in the deterministic audit snapshot. A failed review transaction rolls back both the rule update and its history entry. The database trigger also creates the history row for qualifying direct SQL review updates, so a caller cannot update the review state without a matching history row through ordinary SQL statements.

## Policy review boundary

A fetched document is evidence, not permission. Candidate role suggestions are not legal interpretations. New rules remain `NEEDS_REVIEW`. A rule review is accepted only when the registry is configured with a trusted `ReviewerVerifier` adapter and receives a signed assertion that proves the issuer, signature, audience, key status, authentication time, expiry, subject, company, capability, and decision scope. The verifier must issue a durable signed authorization receipt and re-verify it during each evaluation, including revocation. A reviewer label or local ID is never authentication. Legacy approvals without receipts remain blocked. The repository currently defines the verifier contract and fail-closed enforcement, but **does not yet include a production identity-provider adapter**; therefore the production registry must be initialized without a verifier and all reviews remain blocked until that adapter is implemented and independently configured. The included test verifier is a test double only and must never be used in production. A verified rule must separately declare a structured `ALLOW` or `DENY` effect; the natural-language statement is retained as evidence context and is never parsed as the decision effect. A missing/unknown effect blocks evaluation, and any verified `DENY` takes precedence over every `ALLOW`. The engine does not infer that an API is enabled, an affiliate application is accepted, or commercial content rights exist. Evidence excerpts must match the cited snapshot exactly. SQLite triggers protect records from ordinary UPDATE/DELETE statements, but they are not a cryptographic tamper-proof ledger against an operator who can alter the database file or drop triggers. `ALLOWED` remains an internal policy-engine result, not a live commercial authorization. Do not use it to enable affiliate operations until a production identity provider, policy completeness checks, and independently anchored tamper-evident audit evidence are implemented.

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
