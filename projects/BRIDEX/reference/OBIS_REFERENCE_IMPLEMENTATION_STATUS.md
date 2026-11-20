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
- [x] HMAC-SHA256 request and response integrity for local loopback tests.
- [x] Candidate `OBIS-TLS-MTLS-1` reference binding using Python `ssl` / OpenSSL, TLS 1.3 only, mutual certificate authentication, and no shared HMAC secret.
- [x] TLS endpoint hostname verification plus exactly-one URI SAN peer identity `urn:obis:peer:<lowercase-UUID>`.
- [x] Certificate SHA-256 fingerprint binding to a single configured credential/principal record.
- [x] Mandatory `http/1.1` ALPN, bounded handshake/request timeouts, and no plaintext fallback for mTLS clients.
- [x] Local credential revocation for subsequent requests in the running process.
- [x] Positive and negative mTLS tests using ephemeral test certificates; no private keys are committed.
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
The draft JSON Schema 2020-12 artifact is published at `standards/http/1.1/message.schema.json` and packaged with the reference peer. CI validates the schema and checks the packaged copy against the canonical artifact. Runtime schema negotiation and automatic schema-driven validation are not implemented.


- Production approval of the `OBIS-TLS-MTLS-1` candidate profile.
- Owner-operated CA/trust-anchor lifecycle, certificate issuance/renewal, trust-bundle distribution, durable revocation state, CRL/OCSP, and emergency trust-anchor replacement.
- Durable revocation across process restarts and in-flight operation cancellation.
- Durable/distributed replay protection and idempotency ledger.
- Runtime schema negotiation and automatic schema-driven payload validation.
- Asynchronous operation lifecycle.
- Production audit persistence and tamper-evident evidence.
- Production-hardened non-loopback operations, rate limiting, deployment hardening, and independent security review. The candidate mTLS binding can bind beyond loopback, but is not production-approved.
- Cross-language interoperability suite.

## Release gates before OBIS 1.0.0

1. Freeze normative JSON Schemas and canonicalization rules.
2. Owner/security reviewers approve or revise the `OBIS-TLS-MTLS-1` candidate and its URI SAN mapping.
3. Define owner-operated credential issuance, rotation, revocation, trust-bundle distribution, and principal delegation.
4. Define durable replay/idempotency and outcome reconciliation.
5. Define signed evidence/audit formats and retention controls.
6. Implement at least one independent second-language peer.
7. Pass cross-implementation positive and negative conformance suites.
8. Verify portable operation from a clean environment with TRADIX and BRIDEX unavailable.
9. Complete threat-model review and security testing.
10. Run the ECOSCAN adapter against this BRIDEX loopback peer in a combined cross-project integration test; the current two projects test their adapter and peer halves independently.

A passing local test suite proves only the implemented reference behavior. It does not establish production security or universal interoperability.


## Latest ECOSCAN capability branch verification note

PR #66's latest OBIS capability/resource-grant changes are included as the base of PR #74. GitHub Actions run `44733556568` completed successfully on the PR #74 merge commit, ran 68 tests, and built/installed the OBIS reference wheel. PR #66's branch head is still not independently merged or promoted. The additional TLS/mTLS implementation in PR #75 requires its own CI run on the latest PR #75 head before it can be considered verified.
