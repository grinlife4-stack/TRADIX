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


## Latest combined branch verification

The current combined BRIDEX/TIIS/OBIS work is in Draft PR #72 at head `3c3168f0448fb6ab126f4c3aac2faa6b2d8f2779`.

- GitHub Actions run `44734649269` completed successfully.
- 118 Python tests passed, including the credential-bound ECOSCAN inventory capability and its resource-grant checks.
- Go OBIS reference unit tests passed.
- Python OBIS client ↔ Go OBIS peer loopback HTTP request/response passed.
- BRIDEX Core generated an independent Bridge project; manifest validation, vendored OBIS schema presence, and generated-project wheel build passed.
- TRADIX, OBIS Python, ECOSCAN, and BRIDEX Core wheels built and were installed into isolated targets; packaged schema checks passed.

The combined ECOSCAN adapter-to-BRIDEX OBIS wire test remains intentionally deferred. The ECOSCAN adapter and BRIDEX provider capability are not yet joined into a live cross-project integration. No production endpoint, non-loopback listener, production credential, deployment, or production security profile has been used.


## TLS 1.3 mTLS candidate implementation

Both reference paths now support an opt-in TLS 1.3 mutual-authentication candidate:

- Python reference client and server build owner-supplied SSL contexts with certificate verification required, TLS 1.3 only, and ALPN http/1.1.
- Python server maps the client certificate's single URI SAN urn:obis:peer:<peer-id> to the OBIS sender field and configured credential peer.
- Go reference server requires a client certificate, TLS 1.3, ALPN http/1.1, validates the certificate chain against an owner-supplied CA bundle, and applies the same URI-SAN-to-peer binding.
- The cross-language test creates ephemeral CA/server/client certificates and exercises Python-to-Go mTLS request/response. It also exercises the Python server with the same client certificate.
- The Go reference listener is explicitly loopback-only in both HTTP and HTTPS modes.

Still open before production: owner-approved trust model, CA/issuance ownership, certificate rotation and revocation, trust-bundle expiry/freshness, emergency denylisting, key custody, complete negative certificate tests, independent security review, and removal or replacement of the HMAC development authentication layer. The TLS implementation is a candidate profile, not production approval.


## Latest TLS candidate verification

Draft PR #76 head `c67e7bde0a215673a432c4ca22031bdd31909fde` passed GitHub Actions run `44736402319`:

- 119 Python tests passed.
- Go reference peer unit tests passed.
- Python client to Go server TLS 1.3 mTLS request/response passed using ephemeral certificates.
- Python TLS server/client mTLS request/response passed.
- The generated Bridge template's OBIS peer is byte-identical to the Python reference peer.
- TRADIX, OBIS Python, ECOSCAN, and BRIDEX Core packaging checks passed; generated Bridge wheel build passed.

This validates the candidate's loopback implementation only. It does not close certificate lifecycle, revocation, trust-bundle freshness, emergency response, independent security review, or production authorization gates.
