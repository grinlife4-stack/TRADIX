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
- [x] Candidate `OBIS-TLS-MTLS-1` reference binding in Python `ssl` / OpenSSL and Go `crypto/tls` / `crypto/x509`, TLS 1.3 only, mutual certificate authentication, and no shared HMAC secret.
- [x] TLS endpoint hostname verification plus exactly-one URI SAN peer identity `urn:obis:peer:<lowercase-UUID>`.
- [x] Certificate SHA-256 fingerprint binding to a single configured credential/principal record.
- [x] Mandatory `http/1.1` ALPN, bounded handshake/request timeouts, and no plaintext fallback for mTLS clients.
- [x] Python local credential revocation for subsequent requests in the running process.
- [x] Positive and negative mTLS tests using ephemeral test certificates; no private keys are committed.
- [x] Independent Go peer/client with matching certificate URI and SHA-256 fingerprint-to-credential binding.
- [x] Bidirectional Python client → Go server and Go client → Python server mTLS request/response tests, plus same-URI/different-fingerprint rejection.
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


- Production approval of the `OBIS-TLS-MTLS-1` candidate profile.
- Owner-operated CA/trust-anchor lifecycle, certificate issuance/renewal, trust-bundle distribution, durable revocation state, CRL/OCSP, and emergency trust-anchor replacement.
- Durable revocation across process restarts and in-flight operation cancellation.
- Durable/distributed replay protection and idempotency ledger.
- Runtime schema negotiation and automatic schema-driven payload validation.
- Asynchronous operation lifecycle.
- Production audit persistence and tamper-evident evidence.
- Production-hardened non-loopback operations, rate limiting, deployment hardening, and independent security review. The candidate mTLS binding can bind beyond loopback, but is not production-approved.
- Broader cross-language conformance beyond the current loopback scenarios, including shared malformed-message, expiry, replay, and revocation vectors.

## Release gates before OBIS 1.0.0

1. Freeze normative JSON Schemas and canonicalization rules.
2. Owner/security reviewers approve or revise the `OBIS-TLS-MTLS-1` candidate and its URI SAN mapping.
3. Define owner-operated credential issuance, rotation, revocation, trust-bundle distribution, and principal delegation.
4. Define durable replay/idempotency and outcome reconciliation.
5. Define signed evidence/audit formats and retention controls.
6. Maintain the independent Go implementation with separate ownership/CI and keep it behaviorally aligned with the Python reference.
7. Expand cross-implementation positive and negative conformance beyond the current loopback scenarios.
8. Verify portable operation from a clean environment with TRADIX and BRIDEX unavailable.
9. Complete threat-model review and security testing.
10. Run the ECOSCAN adapter against this BRIDEX loopback peer in a combined cross-project integration test; the current two projects test their adapter and peer halves independently.

A passing local test suite proves only the implemented reference behavior. It does not establish production security or universal interoperability.


## Current OBIS implementation sequence

This OBIS implementation is carried in Draft PR #78, stacked on the unified BRIDEX Engine branch (PR #77), which itself is stacked on the TIIS/TRADIX tooling integration (PR #70). The older parallel OBIS branches (#72, #75, #76) are reference material only and are not dependencies of this branch.

Latest validated PR #78 head: `c8bfad55098065ba1cde50fbd252563a160e745e`.

- OBIS conformance run `44743121177` completed successfully: **57 Python tests passed**, Go reference tests passed (`example.com/bridex/obis-go/peer`), the Python wheel built and installed in an isolated target, schema copies were byte-identical, and the installed package imported without TRADIX or BRIDEX Engine.
- Shared repository run `44743120802` completed successfully: **104 TRADIX tests passed**.
- The BRIDEX Engine dependency on PR #77 was separately validated: run `44742859047` completed successfully with **27 BRIDEX Engine tests passed**.

The Go mTLS path uses no HMAC secret and binds the certificate URI and SHA-256 fingerprint to the configured peer credential. Python and Go exercise both directions over TLS 1.3 mTLS using ephemeral certificates, including same-URI/different-fingerprint rejection. These results validate the loopback candidate only; they do not approve production use.
