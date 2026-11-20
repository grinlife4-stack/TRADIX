# OBIS / TIIS Contract Alignment Audit

**Document ID:** OBIS-TIIS-ALIGN-AUDIT-001  
**Status:** Review findings only; no normative contract change  
**Reviewed ref:** `docs/ecosystem-equipment-model-2026-11-19`  
**Reviewed head:** `4b09ca6cd21675d033d749b0ca3ed350a9f068a9`  
**Review date:** 2026-11-20

## 1. Scope

This audit compares the draft OBIS 0.1 specification, its canonical JSON Schema, the packaged schema copy, the Python reference peer, the TIIS 0.1 specification, the OBIS decision register, and the production security-profile audit.

It is a documentation and contract-consistency review. It does not approve either draft standard, change wire behavior, authorize production deployment, or replace owner/security review.

## 2. Confirmed aligned points

- OBIS is explicitly external, vendor-neutral, and independent of TRADIX/BRIDEX runtime services.
- TIIS is explicitly restricted to authorized TRADIX-internal communication.
- The TIIS specification expressly states that TIIS and OBIS have separate scopes, versioning, schemas, conformance tests, and failure boundaries.
- A Bridge's TIIS-facing adapter is optional; removing it must not break external OBIS operation.
- OBIS canonical schema and packaged schema currently have the same blob SHA: `252cff061c44183fe553d211ab29b5199bf37c07`.
- The Python reference implementation is explicitly loopback-only and its HMAC profile is explicitly development-only. The security audit does not claim production approval.

## 3. OBIS 0.1 envelope/example/schema mismatch

The illustrative request in Section 9 of `docs/OBIS_SPECIFICATION.md` contains fields or representations that the canonical 0.1 schema and Python reference peer reject:

| Item | Specification example | Canonical schema / reference peer |
|---|---|---|
| `sender.bridge_id` | Present | `peerRef` permits only `peer_id`; additional properties are rejected |
| Request `correlation_id` | Present | Not permitted in the request schema/runtime allowlist |
| `issued_at`, `expires_at` | ISO-8601 strings | Numeric timestamps required |
| `evidence_ref` | Present | Not permitted in the request schema/runtime allowlist |

The example is labelled illustrative and not a complete schema, but it is still liable to be copied as a valid message shape. The strict schema and runtime behavior make the difference observable: a message copied from the example is rejected.

### Required owner decisions

1. Decide whether Bridge identity is part of the OBIS 0.1 wire envelope or remains local/configuration metadata. The current core text requires distinct peer and Bridge identities, while the current wire schema/runtime only carry peer identity.
2. Decide whether request correlation/causation metadata and evidence references belong in 0.1, and define their exact semantics if included.
3. Choose one timestamp representation for the normative 0.1 contract. The current schema/runtime use numeric Unix timestamps; the illustrative example uses ISO-8601 strings.
4. Replace or explicitly label the example as non-wire pseudostructure only after these decisions.

Do not silently change the 0.1 schema or runtime. If the wire contract changes incompatibly, version and migration consequences must be assessed before implementation.

## 4. TIIS contract maturity gap

TIIS 0.1 is internally scoped and its architectural boundary is consistent with OBIS. However, its own Section 16 leaves the following open before TIIS 1.0.0:

- Canonical schema dialect and repository layout.
- Internal component identifier format.
- Approved authentication profiles.
- Event delivery and persistence profiles.
- Trace and audit record schema.
- Compatibility/deprecation windows.
- Exact conformance harness and CI integration.

No normative TIIS schema package or versioned compatibility matrix was identified in the reviewed PR file set. Therefore TIIS is currently a draft architecture contract, not a frozen implementer-ready wire contract.

## 5. OBIS production profile remains unapproved

The security audit and decision register agree on the following boundary:

- Python `ssl` / maintained OpenSSL stack is the preferred Python TLS direction.
- Go `crypto/tls` and `crypto/x509` are the leading independent second-peer candidate.
- The current HMAC/loopback profile is development-only.
- Certificate-to-peer identity mapping, SAN rules, trust model, rotation, revocation, stale revocation handling, and production tests remain unresolved.
- No central CA, registry, relay, or TRADIX/BRIDEX runtime is mandatory.

The candidate TLS/mTLS profile must not be marked production-approved until the stated owner, implementation, interoperability, and independent security-review gates pass.

## 6. Gate assessment

| Gate | Assessment | Reason |
|---|---|---|
| CI for reviewed head | Passed | Workflow run #1022 completed successfully |
| PR #42 review state | Open / Draft / unmerged | Owner approval and explicit merge authorization remain outstanding |
| Architecture baseline (Phase 0) | Not closed | Ecosystem master map and execution-order document are still proposed/pending owner review |
| OBIS contract freeze (Phase 1) | Not passed | Envelope/example/schema mismatch and unresolved identity semantics |
| TIIS contract freeze (Phase 1) | Not passed | Normative schemas and several profile decisions remain open |
| Production security | Not passed | Candidate profile and lifecycle are not implemented or independently reviewed |
| Cross-language interoperability | Not passed | Independent second-language peer and shared conformance suite remain outstanding |

## 7. Recommended order of resolution

1. Owner confirms the architecture baseline and the separate authority/scope of OBIS and TIIS.
2. Resolve the four OBIS 0.1 wire-format decisions in Section 3.
3. Publish a canonical OBIS compatibility matrix and test vectors, then ensure schema, reference runtime, examples, and tests agree.
4. Define the TIIS schema layout, identity format, security profiles, event semantics, and compatibility matrix separately.
5. Only then freeze the respective draft contract versions and proceed to production security and independent-peer implementation gates.

## 8. Change-control note

This audit records discrepancies; it does not amend either normative specification or schema. No PR was merged, no deployment was performed, and no credentials or external project connections were provisioned.


## 10. Implementation follow-up — 2026-11-20

The following limited corrections were implemented in the consolidated PR #42 review branch after this audit:

- The OBIS 0.1 Section 9 request example now matches the canonical JSON Schema and the reference runtime: numeric Unix timestamps, peer_id references, and no undeclared bridge_id, correlation_id, or evidence_ref request fields.
- A regression test validates the documented request example against the canonical schema.
- The Python reference now offers an optional owner-local SQLite replay guard. It persists nonce acceptance across process restarts, uses an atomic uniqueness constraint, and fails closed with a normalized 503 before capability execution when replay storage is unavailable.
- The default in-memory guard remains available for lightweight development. The SQLite option is not distributed replay protection, a business-operation idempotency ledger, or production security approval.

Validation:
- PR #42 head: 1d7d8a58b92469c34cee147a6ec330c8fa92c15b.
- CI run #1047 completed successfully, including the complete Python test suite and independent wheel build/install/schema-package checks for OBIS and ECOSCAN.
- PR #42 remains Draft and unmerged.

The following gates remain open: normative OBIS identity and extension decisions; TIIS schema/profile freeze; production TLS/mTLS and certificate-to-peer mapping; credential lifecycle and revocation; business-operation idempotency and unknown-outcome reconciliation; durable audit/evidence records; independent second-language peer; cross-language conformance; and combined ECOSCAN-to-OBIS integration. No production readiness claim follows from this implementation follow-up.


## 11. Independent second-language peer follow-up — 2026-11-20

An independently buildable Go 1.23 peer was added at `projects/BRIDEX/reference/obis-go`. It uses the Go standard library and does not import or execute the Python reference, BRIDEX Core, or TRADIX runtime services. It currently supports the OBIS 0.1 development HMAC profile, strict JSON parsing, request-envelope validation, peer/principal binding, scoped capability authorization, in-memory nonce replay rejection, and a loopback HTTP binding.

Cross-implementation evidence:
- Python reference client → Go peer server: success.
- Go client → Python reference peer server: success.
- Shared OBIS request vectors are exercised by the Go test package.
- CI run #1119 completed successfully on commit `2e06ad11b54e71298d006edbd28168b5fadb4b82`, including Go tests/build, both cross-language success directions, the Python test suite, and package wheel/install checks. CI run #1131 completed successfully on commit `121cdca51ea5812bbc06c709c1e31b06b793be61`, adding signed authenticated error-response coverage in both directions.

This closes only the initial two-peer success-path proof. It does not establish full OBIS Core or Interoperability Conformance. Remaining gaps include broader malformed-input, authentication-failure, replay, timeout, and downgrade tests; TLS/mTLS and certificate-to-peer mapping; credential rotation/revocation; durable replay and business-operation idempotency/outcome reconciliation; audit persistence; and clean-environment portability with TRADIX/BRIDEX unavailable. HMAC remains development-only; no production profile or deployment is approved.


## 12. Go negative and transport-failure follow-up — 2026-11-20

The independent Go peer's negative test coverage was extended without changing the normative OBIS schema, wire envelope, or production security decisions.

Added test coverage includes malformed envelope cases (unknown/missing fields, nested-object shape, empty/duplicate scopes, timestamp type, expiry and TTL), authentication and identity rejection (unknown key, invalid signature, sender/recipient/principal mismatch), scope denial before capability execution, and replay rejection without a second capability execution. CI run #1147 passed on commit `f39c24553e53b6bbf475de195eb4e8c7be72cc3c`.

The Go client also gained tests for request timeout against a non-responsive loopback peer and connection failure against an unavailable loopback endpoint. CI run #1148 passed on commit `7da228cfe799e6b1cef4b87dac83017effd52148`, including Go tests/build, the complete Python/BRIDEX Core/OBIS/ECOSCAN suite, and isolated package wheel/install/schema checks.

This closes only these specific development-profile test cases. It does not establish production transport security, complete cross-language negative conformance, durable replay/idempotency, audit persistence, or release readiness. No normative contract or security profile was changed.


## 13. Cross-peer malformed-envelope and authentication rejection — 2026-11-20

The cross-language integration harness was extended to submit raw OBIS request envelopes to both the independent Go server and the Python reference server. It verifies rejection of a signed unsupported-version envelope (HTTP 426) and a valid-shape request with an invalid HMAC (HTTP 401). For the Python reference peer, the test additionally asserts that the registered capability handler is never invoked for either rejected request.

CI run #1151 passed on commit `e65da4841226d25ac93feb98487d11323b11de63`, including Go tests/build, the complete Python/BRIDEX Core/OBIS/ECOSCAN test suite, and isolated wheel/install/schema checks.

Scope limitation: this is server-side negative coverage for two independent implementations, not a complete bidirectional negative matrix for every malformed/authentication/replay/transport condition. No normative OBIS schema, wire behavior, TIIS contract, or production security decision was changed. HMAC remains development/conformance-only.


## 14. Go client signed-response negative matrix — 2026-11-20

The independent Go client was extended to reject correctly signed but contract-invalid peer responses: downgraded protocol version, mismatched correlation, wrong sender identity, unexpected response fields, and malformed structured error objects. These tests use a loopback peer to ensure rejection occurs after signature verification but before a response is accepted by the caller.

CI run #1154 passed on commit `0a58ebe18cabb58feab1a9eb8c512186aeb2c1ee`, including Go tests/build, the complete Python/BRIDEX Core/OBIS/ECOSCAN suite, and isolated wheel/install/schema checks.

This is a selected Go client response-validation matrix. It is not protocol version negotiation, a complete cross-language downgrade suite, or production security approval. Unsupported versions remain rejected; no negotiation semantics or normative wire contract were added.


## 15. Go durable replay and Python client response validation — 2026-11-20

The Go reference peer now offers an optional owner-local file-backed replay guard implemented using only the Go standard library. It atomically claims each credential-scoped nonce with exclusive file creation, syncs the marker and containing directory before allowing capability execution, and rejects duplicate claims across independently constructed guard instances/processes. Storage and durability errors fail closed with a normalized HTTP 503 before the capability handler runs. The in-memory guard remains the default for development; the file-backed guard is opt-in and must be configured before serving.

Marker files are deliberately retained permanently. No automatic expiry cleanup is implemented because deletion introduces concurrency and clock-related replay-window risks. Consequently, storage consumption grows without bound and must be monitored by the Bridge owner. This is local durable nonce replay protection, not distributed replay coordination, business-operation idempotency, or unknown-outcome reconciliation.

Tests cover persistence across guard recreation, concurrent duplicate claims across guard instances, and fail-closed behavior when storage disappears. CI run #1161 passed on commit `e75432a3dfac92bca93fd4a9bb1dd3d497b8fef4`, including Go tests/build, the complete Python/BRIDEX Core/OBIS/ECOSCAN suite, and isolated package wheel/install/schema checks.

Separately, the Python reference client now rejects selected correctly signed but contract-invalid responses: unsupported/downgraded version, mismatched correlation, wrong sender peer, unexpected fields, and malformed signed error objects. CI run #1157 passed on commit `36bdf84ad248367dd17b455544af1217a9ffab2b`.

No normative OBIS schema, wire envelope, TIIS contract, version negotiation semantics, or production security profile was changed. Remaining gates include complete cross-language negative parity, distributed replay policy where needed, business-operation idempotency/outcome reconciliation, production audit persistence, TLS/mTLS, credential lifecycle, and independent security review. HMAC remains development/conformance-only.
