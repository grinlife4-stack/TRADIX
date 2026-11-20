# OBIS Reference Implementation — Execution Status

**Status:** Executable development/conformance prototype  
**OBIS target:** Draft 0.1.0  
**Implementation:** Standalone Python reference peer  
**Production approval:** Not approved

## Implemented

- [x] Standalone installable package with no TRADIX/BRIDEX runtime imports.
- [x] Direct peer-to-peer request/response over loopback HTTP.
- [x] Protocol/version, strict envelope-field, payload-size, and TTL validation.
- [x] Explicit credential-to-peer and credential-to-principal binding.
- [x] HMAC-SHA256 request and response integrity for local tests.
- [x] Capability registration and receiver-side scope authorization.
- [x] Nonce replay rejection within one running process.
- [x] Correlation ID verification.
- [x] Signed, correlated error envelopes for authenticated request failures.
- [x] Draft JSON Schema 2020-12 artifact and schema-validation tests.
- [x] Positive integration test and negative security/validation tests.

## Deliberately not implemented

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

A passing local test suite proves only the implemented reference behavior. It does not establish production security or universal interoperability.
