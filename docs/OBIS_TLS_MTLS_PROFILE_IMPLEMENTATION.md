# OBIS-TLS-MTLS-1 — Python Reference Candidate

**Status:** Executable reference candidate; not a normative amendment and not production-approved  
**Implementation:** `projects/BRIDEX/reference/obis-python`  
**Profile ID:** `OBIS-TLS-MTLS-1`  
**ALPN:** `http/1.1`

## 1. Purpose and boundary

This document records the current Python reference implementation of the OBIS TLS/mutual-TLS candidate. It is evidence for owner and security review, not a decision that the profile is ready for production.

The implementation reuses Python's `ssl` module and the platform OpenSSL stack. It does not implement cryptographic primitives, X.509 path validation, a CA, or a custom TLS protocol.

## 2. Transport requirements implemented

- HTTPS only when the mTLS mode is selected.
- TLS 1.3 only: client and server contexts must set both minimum and maximum versions to TLS 1.3.
- The client requires certificate-chain validation and endpoint hostname verification.
- The server requires a client certificate (`CERT_REQUIRED`).
- Both sides must negotiate ALPN `http/1.1`; absence or mismatch is rejected.
- The server bounds TLS handshake time and HTTP request time.
- The client has a finite request timeout.
- No HMAC shared secret is accepted in the mTLS client or credential record.
- The existing HMAC profile remains a loopback-only development/conformance mechanism. It is not a fallback for mTLS.

The owner supplies preconfigured `ssl.SSLContext` objects, certificate chains, private-key paths, and trust anchors. The reference package does not create or store private keys.

## 3. Peer identity mapping

The candidate URI SAN format is:

`urn:obis:peer:<lowercase-canonical-UUID>`

Rules enforced by the Python reference:

1. The server endpoint is first validated by the TLS implementation against the configured DNS name or IP address. CN fallback is not used.
2. The server certificate must contain exactly one URI SAN in the OBIS peer URI format. The client compares it exactly with its configured `remote_peer_id`.
3. The TLS server requires a client certificate. The server extracts exactly one URI SAN and the SHA-256 fingerprint of the DER certificate.
4. The server maps the certificate URI and fingerprint to one configured credential record. That record also binds the OBIS peer ID, principal reference, allowed scopes, and optional project/source resource grants.
5. The certificate URI must equal the credential's configured peer ID.
6. A certificate fingerprint cannot be assigned to more than one credential record in the same peer.
7. A peer may have multiple distinct active certificate fingerprints during an explicitly managed rotation window; each remains a separate credential record.

A valid certificate authenticates a peer under the configured trust model. It does not grant a capability. The peer still checks the claimed sender/recipient, principal, capability, scopes, resource grants, expiry, and replay nonce.

## 4. Credential lifecycle behavior

The reference provides `OBISPeer.revoke_credential(key_id)` to remove a local credential record. Subsequent requests using that record are rejected.

This is process-local state only. It is not a distributed revocation protocol, does not persist across restart, and does not cancel an operation that already passed authorization and entered its handler. Certificate renewal, trust-bundle distribution, CRL/OCSP, emergency trust-anchor replacement, and durable revocation remain unimplemented.

## 5. Error and evidence semantics

In mTLS mode, response confidentiality and integrity rely on the authenticated TLS channel. The implementation does not attach an HMAC response signature and does not claim portable detached signatures or non-repudiation.

Authenticated capability/authorization failures return correlated OBIS error responses over the TLS channel. Errors before the application has established an authenticated credential do not disclose a signed application response.

The in-memory nonce replay guard remains process-local. Durable replay protection, idempotency ledgers, outcome reconciliation, and tamper-evident audit are not implemented.

## 6. Tests

The test suite creates ephemeral CA, server, and client certificates in temporary test directories. It exercises:

- Valid TLS 1.3 mTLS request/response.
- Authenticated authorization denial.
- Client certificate URI/fingerprint mismatch.
- Server certificate URI mismatch.
- Missing client certificate.
- Untrusted server CA.
- TLS 1.2-only context rejection.
- Missing OBIS ALPN rejection.
- Plaintext HTTP fallback rejection.
- Local credential revocation.

No test or production private key is committed.

## 7. Remaining production gates

Before this candidate can be approved:

1. Owner/security review of the URI SAN format, trust model, certificate profile, and one-certificate-to-one-credential mapping.
2. Owner-controlled CA or pinning operations, issuance, renewal, rotation, trust-bundle distribution, durable revocation, and emergency response.
3. A documented and tested CRL/OCSP or offline revocation strategy with stale-state failure rules.
4. Durable replay/idempotency and outcome reconciliation.
5. Rate limits, concurrency limits, operational monitoring, and durable audit controls.
6. An independent second-language implementation, preferably Go `crypto/tls` / `crypto/x509`, maintained separately.
7. Shared positive and negative cross-implementation conformance vectors.
8. Independent security review with no unresolved critical/high findings.
9. Separate owner approval for any production deployment.

A successful Python CI run proves only that the tested reference behavior works. It does not prove production security, certificate lifecycle completeness, or universal OBIS interoperability.
