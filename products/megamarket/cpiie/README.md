# MegaMarket CPIIE read-only core

This is the first executable slice of the Company Policy Intelligence & Interaction Engine. It is isolated under `products/megamarket/cpiie`; it is not part of the generic TRADIX core.

## Implemented

- Register company-specific official source metadata using HTTPS URLs.
- Fetch one explicitly registered URL only after its exact hostname is allowlisted by the caller.
- Reject IP-literal/local source URLs, non-public DNS answers, cross-host or cross-port redirects, unsupported content types, invalid text encodings, empty responses, and documents over the configured byte limit.
- Pin the HTTPS connection to the validated public DNS address to reduce DNS-rebinding and SSRF risk.
- Apply request timeouts and a fixed read-only user agent. No cookies, credentials, form submissions, or link crawling.
- Record document snapshots with SHA-256 hashes and per-source versions.
- Record evidence locators and excerpts tied to an exact document snapshot.
- Propose policy rules. Every new rule starts as `NEEDS_REVIEW`.
- Require an explicit human reviewer to mark a rule `VERIFIED`, `CONFLICT`, or `EXPIRED`.
- Fail closed when policy is absent, unreviewed, conflicting, expired, or older than a caller-configured freshness limit.
- Export a deterministic audit snapshot without exporting full document bodies.

## Fetching example

```python
from products.megamarket.cpiie import CPIIERegistry, Source
from products.megamarket.cpiie.fetch import OfficialSourceFetcher

registry = CPIIERegistry("megamarket-policy.sqlite3")
registry.register_source(Source(
    source_id="company-a-affiliate-terms",
    company_id="company-a",
    role="affiliate-terms",
    url="https://official.example.org/affiliate/terms",
    title="Official affiliate terms",
))
fetcher = OfficialSourceFetcher(registry)
receipt = fetcher.fetch(
    "company-a-affiliate-terms",
    allowed_hosts={"official.example.org"},
)
print(receipt.document.content_sha256, receipt.document.version)
```

The example hostname is illustrative, not a selected retailer or active connection. Host allowlisting is an explicit caller decision and must be grounded in a verified official company domain. The fetcher also rejects non-public DNS results and pins the connection to the validated address.

## Explicitly not implemented

- No crawling, sitemap discovery, scheduled polling, or automatic source discovery.
- No PDF parsing, LLM extraction, automatic rule verification, or legal interpretation.
- No company-specific adapters, credentials, OAuth, affiliate links, or account access.
- No forms, emails, support tickets, API mutations, or other external interaction.
- No retailer, affiliate program, country, or category is selected or assumed.

The fetcher records content retrieved from the registered URL; it does not prove that the URL is authoritative or that a company granted commercial permission. A fetched document is evidence for human review, not authorization.

## Run tests

From the repository root:

```bash
python -m pytest -q
```

The implementation uses only the Python standard library and supports Python 3.11+.
