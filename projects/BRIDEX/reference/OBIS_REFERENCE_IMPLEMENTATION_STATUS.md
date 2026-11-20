# OBIS Reference Implementation — Execution Status

**Status:** Executable development/conformance prototype  
**OBIS target:** Draft 0.1.0  
**Implementation:** Standalone Python reference peer  
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
- [x] Correlation ID verification.
- [x] Signed, correlated error envelopes for authenticated request failures.
- [x] Draft JSON Schema 2020-12 artifact and schema-validation tests.
- [x] Positive integration test and negative security/validation tests.

## Deliberately not implemented
The draft JSON Schema 2020-12 artifact is published at `standards/obis/0.1/message.schema.json` and packaged with the reference peer. CI validates the schema and checks the packaged copy against the canonical artifact. Runtime schema negotiation and automatic schema-driven validation are not implemented.


- Production TLS or mutual TLS.
- Production identity issuance, asymmetric signing, trust-anchor management, key rotation, or revocation service.
- Durable/distributed replay protection and idempotency ledger.
- Runtime schema negotiation and automatic schema-driven payload validation.
- Asynchronous operation lifecycle.
- Production audit persistence and tamper-evident evidence.
- Non-loopback transport binding.
- Cross-language interoperability suite.

## Release gates before OBIS 1.0.0

1. Freeze normative JSON Schemas and canonicalization rules.
2. Select and review production authentication and transport security profiles.
3. Define credential issuance, rotation, revocation, and principal delegation.
4. Define durable replay/idempotency and outcome reconciliation.
5. Define signed evidence/audit formats and retention controls.
6. Implement at least one independent second-language peer.
7. Pass cross-implementation positive and negative conformance suites.
8. Verify portable operation from a clean environment with TRADIX and BRIDEX unavailable.
9. Complete threat-model review and security testing.
10. Run the ECOSCAN adapter against this BRIDEX loopback peer in a combined cross-project integration test; the current two projects test their adapter and peer halves independently.

A passing local test suite proves only the implemented reference behavior. It does not establish production security or universal interoperability.
