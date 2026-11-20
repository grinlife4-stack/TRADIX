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
- [x] Nonce replay rejection within one running process in both peers, plus optional owner-local durable Go file-backed replay claims across guard/process restarts.
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
- Distributed replay protection and a durable business-operation idempotency/outcome ledger. The Python SQLite and Go file-backed guards persist nonce replay state for one owner-operated Bridge instance; neither reconciles unknown side-effect outcomes.
- Asynchronous operation lifecycle.
- Production audit persistence and tamper-evident evidence.
- Non-loopback transport binding.
- Full cross-language positive/negative conformance matrix and combined ECOSCAN-to-Go-peer integration.

## Release gates before OBIS 1.0.0

1. Freeze normative JSON Schemas, compatibility rules, and canonicalization rules.
2. Select and independently review production authentication and transport security profiles.
3. Define credential issuance, rotation, revocation, and principal delegation.
4. Complete distributed replay policy where required, business-operation idempotency, and unknown-outcome reconciliation. Local durable nonce guards now exist independently in Python and Go but do not solve side-effect outcome ambiguity.
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


## Go client signed-response rejection matrix — 2026-11-20

The Go client now has tests using a loopback peer that returns correctly HMAC-signed but invalid responses. It must reject:
- A downgraded protocol version.
- A mismatched correlation ID.
- A response claiming the wrong sender peer.
- An unexpected response field.
- A malformed signed error object containing an undeclared field.

CI run #1154 completed successfully on commit `0a58ebe18cabb58feab1a9eb8c512186aeb2c1ee`. It passed Go tests/build, the full Python/BRIDEX Core/OBIS/ECOSCAN suite, and isolated package wheel/install/schema checks.

This is client-side validation coverage for selected signed response failures. It does not implement protocol version negotiation; unsupported versions are rejected. It does not establish complete downgrade protection across future negotiation profiles or production security.


## Go durable replay guard and Python response-validation follow-up — 2026-11-20

The Go peer now supports an optional owner-local `FileReplayGuard` implemented with the Go standard library. Exclusive file creation provides an atomic nonce claim across guard instances/processes. The marker file and containing directory are synced before the capability handler can execute. Duplicate claims return the replay error; storage/write/sync failures return a normalized 503 and fail closed before capability execution. The default in-memory guard remains available for development.

The durable marker files are intentionally retained permanently. Automatic expiry cleanup was not added because cleanup races or clock assumptions could reopen replay windows. This creates unbounded storage growth and requires owner monitoring and an explicit future retention design. The mechanism is local durable replay protection only; it is not distributed replay coordination, a business-operation idempotency ledger, or unknown-outcome reconciliation.

Tests cover persistence after constructing a new guard, atomic duplicate exclusion across concurrent guard instances, and storage failure preventing capability execution. The same test suite continues to cover replay rejection without second execution.

The Python reference client now has a separate signed-response negative test set for downgraded version, wrong correlation, wrong sender, unexpected fields, and malformed signed errors. CI run #1157 passed on commit `36bdf84ad248367dd17b455544af1217a9ffab2b`.

The Go durable replay implementation and tests passed in CI run #1161 on commit `e75432a3dfac92bca93fd4a9bb1dd3d497b8fef4`. The run completed Go tests/build, the complete Python/BRIDEX Core/OBIS/ECOSCAN test suite, and isolated wheel/install/schema checks.

No normative OBIS schema, message envelope, TIIS contract, version negotiation semantics, or production security profile was changed. The Go peer remains loopback-only and HMAC remains development/conformance-only. Full cross-language negative conformance, distributed replay policy, business-operation idempotency/outcome reconciliation, production audit persistence, TLS/mTLS, credential lifecycle, and independent security review remain open.


The standalone Go server CLI now exposes the durable store through optional `--replay-dir`. A cross-language process-restart integration test sends a signed request from the Python test harness to the Go CLI, restarts the Go process with the same replay directory, and verifies the identical request is rejected with HTTP 409. CI run #1166 passed on commit `a81f2960056b397c561efb139b1c9ba396afe317`, including Go tests/build, the complete Python/BRIDEX Core/OBIS/ECOSCAN suite, and isolated wheel/install/schema checks.


A further HTTP-level cross-language test removes the configured Go replay directory after server startup. The Python client receives and validates the Go peer's signed `replay.storage_unavailable` error with HTTP 503; the Go unit test separately verifies that the capability handler is not executed. CI run #1170 passed on commit `afbc6e9f1b877b24ebebcabc06820cee7ccd18a3`, including Go tests/build, the complete Python/BRIDEX Core/OBIS/ECOSCAN suite, and isolated wheel/install/schema checks.


## Python transport-error classification and Go-to-Python negative requests — 2026-11-20

The Python client now distinguishes a request timeout from a peer connection/unavailability failure:
- A direct `TimeoutError` or `socket.timeout`, including the Python 3.12 response-read timeout path, is normalized to `peer.timeout` / HTTP 504.
- A non-timeout `URLError` remains `peer.unavailable` / HTTP 503.

The first CI attempt (#1176) exposed that Python 3.12 can raise `TimeoutError` directly while reading the response rather than wrapping it in `URLError`. The handler was corrected to catch the direct timeout exception, and the separate timeout and connection-failure tests then passed.

The Go-to-Python raw negative integration test sends an authenticated unsupported-version request and an invalid-signature request from the independent Go test harness to the Python peer. The Python capability handler must not execute for either rejected request. CI #1175 passed for this cross-peer test and the full suite. CI #1177 passed on commit `d630ada3683ec0793c818bf1281b5b04aa4f6e12`, including the Go tests/build, full Python/BRIDEX Core/OBIS/ECOSCAN suite, and isolated wheel/install/schema checks.

This remains selected negative-path coverage, not a complete two-way negative conformance matrix. OBIS schema, wire envelope, TIIS contract, version negotiation semantics, and production security profile were not changed. HMAC remains development/conformance-only; production TLS/mTLS, credential lifecycle, distributed replay policy, business-operation idempotency/outcome reconciliation, persistent audit, and independent security review remain open.


## Go-to-Python durable replay across Python process restart — 2026-11-20

The cross-language integration harness now verifies durable replay protection in the opposite direction as well: a Go-originated, correctly signed OBIS request is accepted by the Python peer, then the Python peer process is terminated and restarted against the same owner-local SQLite replay database. The identical Go-originated request is sent again and must receive a signed HTTP 409 `request.replay_detected` response. A durable counter written by the capability handler confirms that the handler ran exactly once and was not re-entered after restart.

The test runs the Go request probe twice against two separate Python peer processes. It verifies response HMAC signatures and correlation IDs on both the initial success and replay rejection. CI run #1185 passed on commit `515079aeb0d4a69494d7dba3b2f6d8cd4d385d1e`, including Go tests/build, the full Python/BRIDEX Core/OBIS/ECOSCAN suite, and isolated wheel/install/schema checks.

This closes the specific local durable replay persistence gap for Go→Python across a real Python process restart, using the same SQLite database. It does not provide distributed replay coordination, business-operation idempotency or unknown-outcome reconciliation, persistent audit/evidence records, or production transport security. HMAC remains development/conformance-only; no normative OBIS schema, wire envelope, TIIS contract, or version negotiation semantics changed.


## Go-originated malformed and expired request rejection by Python peer — 2026-11-20

The independent Go-originated cross-peer negative test now also exercises the Python server's pre-capability rejection paths. It sends an expired but correctly signed request (HTTP 408), a correctly signed request with an undeclared top-level field (HTTP 400), a correctly signed request with an undeclared nested sender field (HTTP 400), malformed JSON (HTTP 400), and duplicate JSON object keys (HTTP 400). Existing authenticated unsupported-version (HTTP 426) and invalid-signature (HTTP 401) checks remain. The Python harness asserts that none of these rejected requests execute the capability handler.

CI run #1187 passed on commit `5b2a7d6dc7e3c3acf8a0c9c6995d8462d695fb88`, including Go tests/build, the full Python/BRIDEX Core/OBIS/ECOSCAN suite, and isolated wheel/install/schema checks.

This extends selected Go→Python server-side negative coverage. It does not complete the full bidirectional negative conformance matrix or production security approval. HMAC remains development/conformance-only; no normative OBIS schema, wire envelope, TIIS contract, or version negotiation semantics changed.


## Python-to-Go malformed and expired request rejection — 2026-11-20

The Python integration harness now sends authenticated and raw malformed requests to the independent Go peer and verifies the server rejects them before capability execution:
- Expired signed request: HTTP 408.
- Unknown top-level field in an otherwise signed request: HTTP 400.
- Unknown nested sender field in an otherwise signed request: HTTP 400.
- Malformed JSON bytes: HTTP 400.
- Duplicate JSON object keys: HTTP 400.

CI run #1189 passed on consolidated PR #42 head `2157d1de0fe60326898615b1b9fd037eac11139e` (run ID `44761677327`). The run completed Go tests/build, the full Python/BRIDEX Core/OBIS/ECOSCAN test suite, and isolated wheel/install/schema checks for BRIDEX Core, OBIS, and ECOSCAN.

This adds selected Python→Go server-side malformed/expired request coverage. It does not establish full bidirectional negative conformance, full signed-error response parity, production security approval, or release readiness. HMAC remains development/conformance-only. No normative OBIS schema, wire envelope, TIIS contract, or version-negotiation semantics changed.


## Go peer authenticated signed-error responses to Python — 2026-11-20

CI run #1194 passed on consolidated PR #42 head `b68cd039cd66b29a4a650a49a46f9420d46d41de` (run ID `44763190803`). The Python integration harness sends correctly signed requests to the independent Go peer and validates the returned error response signature, response envelope, correlation ID, sender/recipient peer identities, HTTP status, and error code for these cases:

- Expired authenticated request: HTTP 408, `request.expired`.
- Unsupported protocol version: HTTP 426, `protocol.unsupported_version`.
- Unknown capability: HTTP 404, `capability.unknown`.
- Unauthorized scope: HTTP 403, `authorization.denied`.
- Repeated nonce after one successful execution: HTTP 409, `request.replay_detected`.

The correction keeps the original signed request unchanged and normalizes only a shallow validation copy for version/time-window checks after HMAC verification. The normalized timestamp values retain the `json.Number` representation expected by strict JSON validation. The Go unit/build checks, complete configured Python test suite, and isolated wheel/install/schema checks for BRIDEX Core, OBIS, and ECOSCAN all passed in the same run.

This closes the selected Python→Go authenticated signed-error response cases listed above. It does not establish full bidirectional signed-error parity, full OBIS conformance, production security approval, distributed replay protection, business-operation idempotency, or durable audit/evidence storage. HMAC remains development/conformance-only. No normative OBIS/TIIS schema, wire contract, or version-negotiation semantics changed.
