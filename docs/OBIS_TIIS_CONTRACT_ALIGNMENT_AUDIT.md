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
