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


## Latest ECOSCAN capability branch verification note

The ECOSCAN inventory capability, credential-bound project/source grant, and three loopback HTTP tests were added on the open Draft PR #66 branch. Current branch head: `7c40d7e81d76a3bb322df809809a1ca41e3f51ab`. The last recorded successful CI remains the earlier head `ae52784ce20f006bade68a35f24d0489bb29be78` with 45 tests. No check run or commit status is recorded for the latest head, so the new capability/resource-grant changes are **not yet CI-verified**. Do not treat the newly added tests as passed until a fresh run completes successfully.


## BRIDEX Core generator 0.1

The standalone BRIDEX engineering-plane package is now implemented at `projects/BRIDEX/core`:

- Dependency-free Python package with `bridex init`, `bridex validate`, and `bridex package`.
- Generated Bridge manifests require explicit owner and operator assignment evidence.
- Generated projects declare OBIS 0.1 and begin with no trusted peers, no enabled capabilities, and draft lifecycle.
- The generated source tree includes its own `pyproject.toml`, README, configuration template, and contract test.
- ZIP export uses fixed timestamps for reproducibility, rejects symlinks, secret-named files, private-key markers, and common token patterns, and returns a SHA-256 digest.
- Root CI now installs and tests BRIDEX Core and builds its wheel. The generated OBIS peer uses the same loopback/HMAC development profile as the reference package; it is not a production transport or security profile. Verification is pending until CI completes on this branch's latest commit.

This generator is an engineering-plane foundation only. It does not implement a production Bridge runtime, network transport, peer authentication, secret lifecycle, or full security scanning of arbitrary source contents.


## Independent Go reference and cross-language development-profile test

A second OBIS 0.1 peer implementation now exists at `projects/BRIDEX/reference/obis-go` using only the Go standard library. It validates the request envelope, credential/principal/peer binding, capability scopes, TTL, replay nonce, and HMAC-SHA256 development profile. The Python OBIS client test starts the Go peer and performs an actual loopback HTTP request/response; the Go suite verifies the shared canonical JSON/HMAC vector and negative authorization/replay cases.

This is cross-language interoperability evidence for the current development profile only. It does not freeze the production canonicalization/signature standard, provide TLS/mTLS, or approve the shared-secret profile for real workloads. CI verification is pending for the latest combined PR head.
