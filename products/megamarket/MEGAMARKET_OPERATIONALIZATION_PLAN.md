# MegaMarket Operationalization Plan

**Status:** Controlled implementation plan; not a production deployment.
**Owner product:** MegaMarket
**Infrastructure boundary:** TRADIX may provide generic build, CI, storage and deployment capabilities. MegaMarket-specific product, compliance, ranking and customer logic remain inside `products/megamarket/`.
**Current branch:** `feat/megamarket-cpiie-readonly-core-2026-11-17`
**Current CPIIE baseline:** `0603cf2cadc2683a5e64191995213d0def37d61d`

## 1. Verified current state

The repository currently contains product specifications, a provider-neutral CPIIE Python package, tests and CI. It does **not** yet contain a deployable MegaMarket storefront, customer API, product catalog service, production database configuration, user authentication, affiliate-link service, or deployment environment for MegaMarket.

The CPIIE package supports source registration, controlled HTTPS fetching, bounded discovery, on-demand monitoring, immutable document snapshots, evidence records, scoped reviewer-assertion verification contracts, policy evaluation and deterministic audit export. The reviewer contract is fail-closed, requires the `policy_reviewer` role, and binds signed assertions to a canonical hash of the exact company, source, document hash/version, evidence ID, rule text/effect/expiry, capability and decision. It prevents cross-rule receipt replay. No production identity-provider adapter is configured; therefore no real reviewer can yet authorize a rule. Its tests use a deterministic test double and are synthetic/code-level validation; they do not establish retailer authority, legal permission, live data rights, commercial approval or production reliability.

The reviewer-identity implementation is currently verified by GitHub Actions run #571 (`44099472148`), successful on commit `4d911173f80747b795f9a37aa4d542cf1a30ae6f`, with 92 passed and 4 subtests passed. This result applies only to that exact commit. The next test addition covers cross-rule receipt replay and will receive its own SHA-matched CI result.

## 2. Non-negotiable operating boundaries

1. No retailer, affiliate network, country, product category, API or data feed is presumed approved.
2. Use only official, explicitly permitted sources and the exact rights granted for each data type and purpose.
3. Price, availability, images, descriptions, reviews, logos and product attributes each require their own applicable usage-rights and freshness checks.
4. Affiliate membership, data/API access, content display rights and permission to create affiliate links are separate facts; one never implies another.
5. Commission and paid placement must not influence product scoring, recommendation order or editorial conclusions. Ranking must not receive commission values.
6. Affiliate relationships must be disclosed clearly wherever required.
7. Fake reviews, fabricated sales, synthetic clicks/orders/conversions, cookie stuffing, misleading attribution and privacy-invasive tracking are prohibited.
8. Unknown, missing, conflicting, expired or stale evidence fails closed.
9. No account credentials, OAuth connection, application submission, contract acceptance, payment, email, support request, order, purchase, checkout, affiliate-link activation or external write operation is permitted during the initial pilot.
10. Human approval is required before any legal commitment, commercial activation, public launch or irreversible external action.

## 3. Current release gates

### Gate A — Repository and evidence integrity
- Keep CPIIE isolated inside MegaMarket.
- Keep PR #35 open and draft until its scope is reviewed; do not merge as part of this plan.
- Verify every CI result against the exact commit SHA.
- Retain test outputs and audit exports independently of the working SQLite database.
- Do not describe SQLite triggers as cryptographic tamper protection.

### Gate B — Reviewer identity and authority
- Implemented in code: free-form reviewer labels no longer authorize reviews; a trusted verifier contract must validate signed assertions and exact company/capability/decision scope.
- Implemented in code: each review stores issuer, subject, key ID, assertion ID, role, scoped claims, authentication window, canonical evidence-context hash and a signed authorization receipt; evaluations re-verify the receipt and fail closed on missing, invalid, expired or revoked receipts.
- Implemented in code: the signed context binds the company, source, document hash/version, evidence ID, rule text/effect/expiry, capability and decision; a receipt cannot be replayed for another rule.
- Implemented in code: direct SQL review updates without a complete receipt are rejected by the SQLite guard; legacy approvals without receipts remain blocked.
- Tested with a deterministic test double only, including scope, role, revocation and cross-rule replay cases. This is not a production identity provider.
- **Still blocked:** select and configure a real identity provider, implement cryptographic signature/JWKS validation, issuer/audience/key-rotation/revocation handling, and provision secrets/keys outside the repository. No real reviewer authentication or commercial authorization is active.

### Gate C — Tamper-evident audit
- Define canonical event serialization and a versioned hash-chain format.
- Include source/document/evidence/rule/review/evaluation events and their causal references.
- Verify the chain on export and import; reject gaps, reordering, duplicate sequence numbers and altered payloads.
- Anchor chain heads outside the SQLite database using a separately controlled signing/retention mechanism.
- Keep private signing keys out of the repository, CI logs and ordinary application data.
- Test tampering with both event rows and source content.

### Gate D — Shadow-mode pilot
- Select one initial market, one product category and a small number of official candidate sources only after those choices are explicitly approved.
- First collect only synthetic fixtures and public policy pages whose access is permitted.
- Keep the pipeline read-only and manually invoked.
- Produce internal product/source evidence records and compliance evaluations; do not publish product pages or affiliate links.
- Compare every extracted policy claim to its exact source passage and record uncertainty.
- Track fetch success, source freshness, evidence coverage, unresolved policy items and false-block/false-allow findings.

### Gate E — Product MVP
Build the missing application layers only after the shadow-mode evidence process is reliable:
- product identity and catalog schema;
- permitted-source ingestion adapters;
- price/availability freshness model;
- product comparison and evidence-backed decision engine;
- customer-facing web experience and search;
- privacy-conscious analytics and observability;
- administrative review interface with authenticated roles.

The recommendation engine must be technically separated from affiliate economics. A CI test must prove that changing commission inputs cannot change ranking output.

### Gate F — Commercial activation
Commercial activation is a separate release requiring, per program and country:
- verified program acceptance and account status;
- explicit data, content, image, price, availability and review usage rights;
- permitted API/feed access and retention rules;
- approved affiliate-link generation and disclosure;
- privacy, consumer-protection, tax and business review appropriate to the launch market;
- authenticated authorized reviewer and independently anchored audit evidence;
- successful staging tests and explicit human release approval.

No item in this gate is currently asserted as complete.

## 4. Pilot acceptance criteria

The read-only pilot is acceptable only when:
- every source has a documented owner, official URL, role, jurisdiction and permitted use;
- every stored claim points to an immutable source snapshot and exact evidence;
- all missing/ambiguous/expired/conflicting permissions block the affected capability;
- stale price/availability data cannot be represented as current;
- every evaluation is reproducible from retained inputs and versioned rules;
- audit-chain verification detects deliberate edits, deletions and reordering;
- no affiliate or commission field is available to the ranking component;
- network access is limited to explicitly allowlisted hosts and only during an operator-triggered run;
- failure, timeout, malformed data or partial execution leaves a visible non-success state;
- no external commercial write or customer transaction is possible.

## 5. Immediate implementation sequence

1. [x] Add fail-closed reviewer assertion contract and scoped authority checks. [ ] Connect a production identity provider and validate its signatures, audience, key rotation and revocation before enabling real reviews.
2. Add signed, independently anchored audit-chain export and tamper tests.
3. Add a documented shadow-mode command and deterministic sample dataset.
4. Add source-by-source rights metadata and freshness policy.
5. Run the pilot against approved sources and inspect the resulting evidence manually.
6. Only then implement the customer-facing MegaMarket MVP and deployment pipeline.
7. Keep commercial activation behind a separate, explicit release gate.

## 6. Operational status vocabulary

- **Implemented:** code exists in the repository.
- **Tested:** automated tests pass on a named commit.
- **Shadow-running:** a controlled read-only run has been performed and its artifacts retained.
- **Commercially authorized:** the specific program, data rights, market and action have documented approval.
- **Production:** deployed, monitored, recoverable and approved for the stated scope.

These terms must not be used interchangeably. A passing test suite is not a shadow run; a shadow run is not commercial authorization; a merged PR is not a production deployment.
