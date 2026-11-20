# OBIS Reference Implementation — Execution Status

**Status:** Executable development/conformance prototypes; bidirectional success, capability-error, and scope-denial paths verified  
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
- [x] Go unit tests consuming the shared OBIS request and response vectors.
- [x] Bidirectional development-profile success-path tests: Python client → Go server and Go client → Python server.
- [x] Bidirectional authenticated error tests for unknown capabilities and denied scopes; Go signs correlated error responses and the Go client verifies signed Python errors.
- [x] Go envelope validators exercised against all published OBIS 0.1 request and response vectors.
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
- Full cross-language positive/negative conformance matrix and combined ECOSCAN-to-Go-peer integration.

## Release gates before OBIS 1.0.0

1. Freeze normative JSON Schemas, compatibility rules, and canonicalization rules.
2. Select and independently review production authentication and transport security profiles.
3. Define credential issuance, rotation, revocation, and principal delegation.
4. Complete durable replay protection, business-operation idempotency, and unknown-outcome reconciliation.
5. Define signed evidence/audit formats and retention controls.
6. Extend Go peer parity and negative coverage to all relevant request/response behaviors, including cross-language malformed-message, replay, downgrade, timeout, and transport-failure cases.
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
- Python reference client → Go peer server: success, unknown capability, and denied scope.
- Go peer client → Python reference peer server: success, unknown capability, and denied scope.
- Go unit tests exercise all published request and response vectors, plus duplicate-key rejection and local nonce replay rejection.

CI run #1119 completed successfully on commit `2e06ad11b54e71298d006edbd28168b5fadb4b82`, proving the initial bidirectional success path. CI run #1131 completed successfully on commit `121cdca51ea5812bbc06c709c1e31b06b793be61`, adding signed authenticated error responses. CI run #1144 completed successfully on commit `87cf0cf0bee44ef8de9eb6d9d3888e07c7e8c074`; it additionally exercised all shared OBIS request/response vectors in Go and bidirectional authorization-denial responses, then ran the full Python suite and isolated wheel/install checks.

This proves bidirectional interoperability for the current loopback development HMAC success path and selected authenticated error cases only. HMAC remains development/conformance-only. Production TLS/mTLS, canonicalization freeze, credential lifecycle, broader malformed/transport cross-language conformance, durable replay and operation idempotency, audit persistence, and independent security review remain open.


## Go negative and transport-failure matrix — 2026-11-20

The Go peer test suite was extended on commit `f39c24553e53b6bbf475de195eb4e8c7be72cc3c` with malformed-envelope, identity/authentication rejection, scope-denial, and replay-no-second-execution cases. CI run #1147 completed successfully.

The Go client tests were then extended on commit `7da228cfe799e6b1cef4b87dac83017effd52148` to verify:
- A non-responsive loopback peer produces a network timeout under the client's configured three-second request timeout.
- A closed/unavailable loopback endpoint produces a connection error.

CI run #1148 completed successfully on that exact commit. The run completed Go tests, Go binary build, the full Python/BRIDEX Core/OBIS/ECOSCAN test suite, and isolated wheel/install/schema checks.

These are local development transport tests, not a production network resilience or security certification. The Go peer still lacks durable replay, business-operation idempotency/outcome reconciliation, production TLS/mTLS, credential lifecycle, persistent audit, full cross-language negative parity, and clean-environment independence evidence.


## Cross-peer malformed and authentication rejection — 2026-11-20

The Python integration harness now sends raw OBIS envelopes to both independently implemented loopback server endpoints and verifies that:
- A structurally invalid/unsupported-version envelope with a valid development HMAC is rejected with HTTP 426.
- A valid request envelope with an invalid HMAC is rejected with HTTP 401.
- The Python peer's registered capability handler is not invoked for either rejected request.

The Go server rejection cases and Python server no-execution cases passed in CI run #1151 on commit `e65da4841226d25ac93feb98487d11323b11de63`. The same run completed Go tests/build, the full Python/BRIDEX Core/OBIS/ECOSCAN test suite, and isolated package wheel/install/schema checks.

This adds server-side negative coverage across the two implementations. It does not yet prove every negative case in both client/server directions, nor does it cover production TLS/mTLS, downgrade negotiation, durable replay across Go restarts, business-operation idempotency/outcome reconciliation, persistent audit, or production readiness.
