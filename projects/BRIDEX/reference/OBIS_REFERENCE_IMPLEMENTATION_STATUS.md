# OBIS Reference Implementation — Execution Status

**Status:** Executable development/conformance prototypes; bidirectional success and initial authenticated-error paths verified  
**OBIS target:** Draft 0.1.0  
**Implementations:** Standalone Python reference peer + independent Go peer  
**Production approval:** Not approved

## Implemented

- [x] Standalone Python package with no TRADIX/BRIDEX runtime imports.
- [x] Independent Go 1.23 package using only the Go standard library; no Python, BRIDEX Core, or TRADIX runtime dependency.
- [x] CI wheel-build and isolated-target install smoke tests, including packaged schema presence.
- [x] Direct peer-to-peer request/response over loopback HTTP.
- [x] Protocol/version, strict request and response envelope-field, payload-size, and TTL validation.
- [x] Authenticated response object/type, peer-reference, correlation, timestamp, and structured-error validation in the Python reference.
- [x] Explicit credential-to-peer and credential-to-principal binding.
- [x] HMAC-SHA256 request and response integrity for local development/conformance tests only.
- [x] Capability registration and receiver-side scope authorization.
- [x] Optional resource-bound capabilities with per-credential project/source allowlists, checked before the capability handler runs.
- [x] ECOSCAN read-only inventory capability `ecoscan.inventory.read@1.0` with strict payload/result validation.
- [x] Loopback HTTP integration tests for a successful ECOSCAN inventory request and denial of an ungranted project/source before provider invocation.
- [x] Client-side scope narrowing prevents requests beyond the configured local grant.
- [x] Capability result JSON serializability and response-size bounds in the Python reference.
- [x] Loopback URL restrictions, finite positive client timeout, HTTP content-type enforcement, and rejection of unsupported transfer encoding.
- [x] Nonce replay rejection within one running process in both peers.
- [x] Optional owner-local SQLite nonce persistence across restarts in Python, with atomic uniqueness and fail-closed storage errors.
- [x] Correlation ID verification and signed, correlated error envelopes for authenticated request failures in Python.
- [x] Draft JSON Schema 2020-12 artifact and schema-validation tests.
- [x] Language-neutral OBIS 0.1 message-schema accept/reject vectors and standalone BRIDEX runner.
- [x] Go unit tests consuming the shared OBIS request vectors.
- [x] Bidirectional development-profile success-path tests: Python client → Go server and Go client → Python server.\n- [x] Initial authenticated error-response tests in both directions using the `capability.unknown` case; Go signs correlated errors and the Go client verifies signed Python error responses.
- [x] CI Go unit tests and binary build, followed by the full Python/BRIDEX Core/OBIS/ECOSCAN test suite with both cross-language tests enabled.

## Deliberately not implemented

The canonical draft JSON Schema 2020-12 artifact is published at `standards/obis/0.1/message.schema.json` and packaged with the Python reference peer. The current Go peer performs its own strict envelope validation; it does not yet provide full schema-driven validation against every published response/request vector.

- Production TLS or mutual TLS.
- Production identity issuance, asymmetric signing, trust-anchor management, key rotation, or revocation service.
- A frozen, language-neutral production canonicalization/signature profile. The current HMAC implementation is a development/conformance binding, not a normative production profile.
- Distributed replay protection and a durable business-operation idempotency/outcome ledger. The optional Python SQLite guard persists nonce replay state for one owner-operated Bridge instance; it does not reconcile unknown side-effect outcomes.
- Asynchronous operation lifecycle.
- Production audit persistence and tamper-evident evidence.
- Non-loopback transport binding.
- Authenticated error-response parity in the Go peer.
- Full cross-language positive/negative conformance matrix and combined ECOSCAN-to-Go-peer integration.

## Release gates before OBIS 1.0.0

1. Freeze normative JSON Schemas, compatibility rules, and canonicalization rules.
2. Select and independently review production authentication and transport security profiles.
3. Define credential issuance, rotation, revocation, and principal delegation.
4. Complete durable replay protection, business-operation idempotency, and unknown-outcome reconciliation.
5. Define signed evidence/audit formats and retention controls.
6. Extend Go peer parity and negative coverage to all relevant request/response behaviors, malformed messages, replay cases, and authorization failures.
7. Pass the full cross-implementation positive and negative conformance suite.
8. Verify portable operation from a clean environment with TRADIX and BRIDEX unavailable.
9. Complete threat-model review and security testing.
10. Run the ECOSCAN adapter against both independently implemented peers in combined cross-project integration tests.

A passing local test suite proves only the implemented reference behavior. It does not establish production security or universal interoperability.

## Latest ECOSCAN capability branch verification note

The ECOSCAN inventory capability, credential-bound project/source grant, and three loopback HTTP tests were synchronized from PR #66 into the consolidated PR #42 review branch.

- PR #66 source head synchronized at content level: `c44b6a87e91531ab4c8333c33b5b71e0f4dde9d0`.
- Consolidated implementation commit in PR #42: `d7271fa2f365d1006ee1d599bb34be319790b5aa`.
- CI run #1014 for the consolidated implementation completed successfully. It ran the Python suite, built OBIS and ECOSCAN wheels, installed both packages in isolated targets, and checked packaged schemas.
- Follow-up documentation-only commit: `ae7f55f52df71a1462dc6fbdbd49c11fd9648a8e`.
- CI run #1016 for that earlier PR #42 head completed successfully.

The two PR branches have not had their commit histories merged; implementation files were synchronized. PR #42 remains Draft and unmerged. PR #66 remains open/Draft for traceability and must not be merged independently.

## Independent Go peer — 2026-11-20

An independently buildable Go 1.23 peer is present at `projects/BRIDEX/reference/obis-go`. It uses only the Go standard library and does not import or invoke the Python reference implementation, BRIDEX Core, or TRADIX services.

The cross-language tests cover both directions:
- Python reference client → Go peer server, including verification of the Go-signed correlated success response.
- Go peer client → Python reference peer server, including verification of the Python-signed correlated success response.

CI run #1119 completed successfully on commit `2e06ad11b54e71298d006edbd28168b5fadb4b82`. It ran Go unit tests, built the Go peer, ran the complete Python/BRIDEX Core/OBIS/ECOSCAN test suite with both cross-language tests enabled, and built/isolated-installed the Python packages.

This proves bidirectional interoperability for the loopback development HMAC success path and an initial authenticated `capability.unknown` error path. CI run #1131 completed successfully on commit `121cdca51ea5812bbc06c709c1e31b06b793be61`; it ran Go unit tests/build, all four cross-language success/error tests, the full Python test suite, and isolated wheel/install checks. HMAC remains development/conformance-only. Production TLS/mTLS, canonicalization freeze, credential lifecycle, broader negative cross-language conformance, durable replay and operation idempotency, audit persistence, and independent security review remain open.
