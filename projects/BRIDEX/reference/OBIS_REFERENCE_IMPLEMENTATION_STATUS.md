# OBIS Reference Implementation — Execution Status

**Status:** Executable development/conformance prototype  
**OBIS target:** Draft 0.1.0  
**Implementations:** Standalone Python reference peer; independent Go peer (early development stage)  
**Production approval:** Not approved

## Implemented

- [x] Standalone installable package with no TRADIX/BRIDEX runtime imports.
- [x] CI wheel-build and isolated-target install smoke test, including packaged schema presence.
- [x] Direct peer-to-peer request/response over loopback HTTP.
- [x] Protocol/version, strict request and response envelope-field, payload-size, and TTL validation.
- [x] Authenticated response object/type, peer-reference, correlation, timestamp, and structured-error validation.
- [x] Explicit credential-to-peer and credential-to-principal binding.
- [x] HMAC-SHA256 request and response integrity for local tests.
- [x] Capability registration and receiver-side scope authorization.
- [x] Optional resource-bound capabilities with per-credential project/source allowlists, checked before the capability handler runs.
- [x] ECOSCAN read-only inventory capability `ecoscan.inventory.read@1.0` with strict payload/result validation.
- [x] Loopback HTTP integration tests for a successful ECOSCAN inventory request and denial of an ungranted project/source before provider invocation.
- [x] Client-side scope narrowing prevents requests beyond the configured local grant.
- [x] Capability result JSON serializability and response-size bounds.
- [x] Loopback URL restrictions and finite positive client timeout.
- [x] HTTP content-type enforcement and rejection of unsupported transfer encoding.
- [x] Nonce replay rejection within one running process.
- [x] Optional owner-local SQLite nonce persistence across restarts with atomic uniqueness and fail-closed storage errors.
- [x] Optional owner-local SQLite replay persistence across process restarts, with atomic uniqueness and fail-closed storage errors.
- [x] Correlation ID verification.
- [x] Signed, correlated error envelopes for authenticated request failures.
- [x] Draft JSON Schema 2020-12 artifact and schema-validation tests.
- [x] Positive integration test and negative security/validation tests.
- [x] Independent Go 1.23 peer using only the Go standard library; it has its own strict parser, request validator, peer/principal binding, scope checks, nonce replay guard, and loopback HTTP server.
- [x] Shared OBIS request-vector tests in Go.
- [x] Cross-language Python-client → Go-server request/response test; CI run #1100 completed successfully on commit `1848b42dc9dd209ebe71bea8562185d5507f6533`.

## Deliberately not implemented
The draft JSON Schema 2020-12 artifact is published at `standards/obis/0.1/message.schema.json` and packaged with the reference peer. CI validates the schema and checks the packaged copy against the canonical artifact. Runtime schema negotiation and automatic schema-driven validation are not implemented.


- Production TLS or mutual TLS.
- Production identity issuance, asymmetric signing, trust-anchor management, key rotation, or revocation service.
- Distributed replay protection and a durable business-operation idempotency/outcome ledger. The optional SQLite guard only persists nonce replay state for one owner-operated Bridge instance; it does not reconcile unknown side-effect outcomes.
- Runtime schema negotiation and automatic schema-driven payload validation.
- Asynchronous operation lifecycle.
- Production audit persistence and tamper-evident evidence.
- Non-loopback transport binding.
- Full cross-language interoperability conformance. The first Python-to-Go success path is implemented and CI-tested; the reverse Go-to-Python path has now been added but its CI result is pending. Error-response parity and broader negative cross-language cases remain open.

## Release gates before OBIS 1.0.0

1. Freeze normative JSON Schemas and canonicalization rules.
2. Select and review production authentication and transport security profiles.
3. Define credential issuance, rotation, revocation, and principal delegation.
4. Complete durable replay protection, business-operation idempotency, and unknown-outcome reconciliation. The optional SQLite nonce guard is implemented but does not yet provide an operation-result ledger.
5. Define signed evidence/audit formats and retention controls.
6. Complete the independent Go peer beyond its initial development transport, including reverse-direction, authenticated-error, and negative cross-language cases.
7. Pass the full cross-implementation positive and negative conformance suite.
8. Verify portable operation from a clean environment with TRADIX and BRIDEX unavailable.
9. Complete threat-model review and security testing.
10. Run the ECOSCAN adapter against both independently implemented peers in a combined cross-project integration test; the current two projects test their adapter and peer halves independently.

A passing local test suite proves only the implemented reference behavior. It does not establish production security or universal interoperability.


## Latest ECOSCAN capability branch verification note

The ECOSCAN inventory capability, credential-bound project/source grant, and three loopback HTTP tests were synchronized from PR #66 into the consolidated PR #42 review branch.

- PR #66 source head synchronized at content level: `c44b6a87e91531ab4c8333c33b5b71e0f4dde9d0`.
- Consolidated implementation commit in PR #42: `d7271fa2f365d1006ee1d599bb34be319790b5aa`.
- CI run #1014 for the consolidated implementation: **completed successfully**. It ran the Python suite, built OBIS and ECOSCAN wheels, installed both packages in isolated targets, and checked packaged schemas.
- Follow-up documentation-only commit: `ae7f55f52df71a1462dc6fbdbd49c11fd9648a8e`.
- CI run #1016 for that current PR #42 head: **completed successfully**.

The two PR branches have not had their commit histories merged; the implementation files were synchronized. PR #42 remains Draft and unmerged. PR #66 remains open/Draft for traceability and must not be merged independently.

These CI results verify only the tests and packaging checks that actually ran. The optional SQLite nonce guard now persists replay state locally, but this does **not** close production security, business-operation idempotency/outcome reconciliation, audit persistence, second-language interoperability, or combined ECOSCAN-to-OBIS integration gates.


## Independent Go peer — 2026-11-20

A second-language peer has been added at `projects/BRIDEX/reference/obis-go`. It is independently buildable, uses only the Go standard library, and does not import or execute the Python implementation. The Go peer supports the local development HMAC profile, direct loopback HTTP, request validation, explicit peer/principal binding, scoped capabilities, and in-memory nonce replay rejection.

- Go unit tests consume the shared OBIS request vectors.
- CI run #1100 completed successfully for commit `1848b42dc9dd209ebe71bea8562185d5507f6533`, including Go tests/build and a Python reference client calling the Go peer and validating its signed response.
- A reverse-direction Go client → Python peer integration test is now included; CI run #1108 is pending at the time of this note.

This is early cross-implementation evidence, not full OBIS Interoperability Conformance. The Go implementation does not yet provide production TLS/mTLS, authenticated error-response parity, durable replay, business-operation idempotency/outcome reconciliation, audit persistence, or complete security-profile conformance. HMAC remains development-only.
