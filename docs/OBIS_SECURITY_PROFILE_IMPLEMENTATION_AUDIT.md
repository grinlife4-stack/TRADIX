# OBIS — Production Security Profile Implementation Audit

**Document ID:** OBIS-SEC-AUDIT-001  
**Status:** Evidence-based implementation audit and design recommendation; owner/security review required  
**Target:** OBIS-TLS-MTLS-1 candidate  
**Applies to:** OBIS 0.1 development and future production profile work  
**Decision authority:** Bridge owner and independent OBIS security reviewers

## 1. Purpose and decision boundary

This audit evaluates whether OBIS should implement transport security and certificate handling itself or reuse maintained TLS/X.509 implementations.

**Decision:** Do not implement cryptographic primitives, TLS, certificate-path validation, or a custom PKI. Reuse the platform's maintained TLS stack. Keep peer authorization, capability scopes, and OBIS identity-to-certificate binding in the OBIS application layer.

This audit does not approve a production security profile, select a final certificate lifecycle, or authorize internet-facing deployment. A separate Python TLS/mTLS candidate reference mode has since been implemented; the HMAC/loopback mode remains development-only.

## 2. Required capabilities

A production candidate must provide:

- TLS 1.3 encrypted transport with server authentication.
- Mutual TLS for peer authentication where the selected profile requires it.
- Strict X.509 path and validity checks using a maintained implementation.
- Explicit binding between authenticated certificate identity and the configured OBIS peer identity.
- Separate authentication and per-capability authorization.
- Owner-controlled trust anchors, certificate issuance, rotation, revocation, and incident response.
- No mandatory central CA, hosted identity provider, TRADIX/BRIDEX service, relay, or registry.
- Cross-language behavior that can be tested independently.
- Safe failure when trust material is missing, expired, revoked, malformed, or stale.

## 3. Ready-made implementation options

| Option | Capability and license | Reuse decision | Limitations / operational risks |
|---|---|---|---|
| Python `ssl` + platform OpenSSL | TLS client/server and X.509 verification through Python's standard library; Python is PSF-licensed and OpenSSL is separately licensed | **Preferred for the Python reference implementation.** No additional runtime dependency is required for TLS itself. | Behavior and supported algorithms depend on Python/OpenSSL build and OS. It does not define OBIS peer mapping, authorization, CA operations, revocation policy, or key custody. Pin and test supported runtime versions. |
| OpenSSL library / CLI | Widely deployed TLS and X.509 implementation; OpenSSL 3.x uses Apache-2.0 licensing | Reuse through maintained language bindings/platform integration; CLI may support local test-certificate generation and diagnostics only. | Do not shell out to OpenSSL for every request or invent a wrapper protocol. The CLI is not a certificate-management policy or a trust model. |
| Go `crypto/tls` and `crypto/x509` | Standard Go TLS and X.509 implementation; Go standard library uses a BSD-style license | **Preferred candidate for the independent second-language peer.** | Must implement the same OBIS-specific certificate-to-peer mapping and negative tests. Independent code is needed; translating Python internals line-for-line is not an independent implementation. |
| Rustls | Maintained Rust TLS implementation with Apache-2.0/MIT licensing | Suitable alternative if a Rust Bridge runtime is selected; not needed for the first Python reference. | Adds a Rust build/runtime choice. Do not add it merely to increase the dependency count. |
| Smallstep `step-ca` | Self-hostable certificate authority and certificate lifecycle tooling; Apache-2.0 | Optional owner-operated PKI candidate for deployments that need automated issuance and renewal. | It introduces a CA service and operational responsibility. It must not become a mandatory OBIS service or a shared TRADIX identity authority. |
| cert-manager / Kubernetes PKI tooling | Certificate issuance/renewal integration for Kubernetes environments | Optional only where the Bridge owner already operates Kubernetes and accepts the dependency. | Kubernetes-specific and unsuitable as a universal Bridge requirement. It does not define OBIS identity or capability authorization. |

## 4. Selected implementation direction

### 4.1 Python reference

- Use Python's standard `ssl` module backed by a maintained OpenSSL build.
- Do not add a third-party TLS implementation to the Python runtime.
- Keep the current loopback HTTP + HMAC mode isolated as a development-only profile.
- A separate TLS integration mode is now present as an implementation candidate; it remains disabled unless an owner supplies an explicitly configured TLS context.
- Keep certificate loading, trust configuration, and private-key paths owner-supplied. Never commit test or production private keys.

### 4.3 Candidate reference profile now implemented

The standalone Python reference contains an implementation candidate named `OBIS-TLS-MTLS-1` (PR #75):

- Python's standard `ssl` module and the platform OpenSSL stack; no custom cryptographic implementation.
- TLS 1.3 only, with server-side client-certificate requirement.
- Mandatory ALPN `obis/0.1`.
- Standard certificate-chain validation and DNS/IP endpoint hostname verification.
- Exactly one canonical URI SAN `urn:obis:peer:<lowercase-UUID>` for the OBIS peer identifier.
- Server-side mapping of the authenticated client certificate URI and SHA-256 certificate fingerprint to one configured credential/principal record.
- Bounded TLS handshake and HTTP request timeouts.
- No HMAC shared secret in the mTLS mode; the existing HMAC mode remains loopback-only.

This implementation does **not** complete the profile lifecycle. It has no CA service, certificate issuance/renewal, trust-bundle distribution, CRL/OCSP, durable revocation state, durable replay ledger, Go implementation, cross-language conformance evidence, or independent security review. The URI scheme and certificate constraints are implementation candidates that still require owner/security approval before they become normative.

### 4.2 Independent second implementation

- Use Go's standard `crypto/tls` and `crypto/x509` packages as the leading candidate for a second-language peer.
- Keep the second implementation in a separate repository or independently buildable package with its own maintainer and CI.
- Run shared positive and negative OBIS conformance vectors against both implementations.
- A second implementation must not import or execute the Python reference.

### 4.3 Certificate authority and trust distribution

Do not mandate a public CA, central CA, hosted identity provider, or automatic certificate service.

Permitted candidate trust models for owner review:

1. **Owner-controlled private PKI:** the peer owner operates or appoints its own CA and distributes trust anchors to explicitly approved peers.
2. **Explicit certificate/key pinning:** peers exchange and verify a specifically approved certificate or public-key identity through an out-of-band owner-controlled process.

A deployment must declare which model it uses. Trust anchors and peer allowlists remain local owner-controlled configuration. Cross-project or cross-Bridge trust is never inferred from portfolio membership.

## 5. Certificate identity rules requiring normative specification

### 5.1 Server identity

- Verify the server identity against the endpoint reference identity.
- Use DNS-ID or IP-ID SAN matching as appropriate to the configured endpoint.
- Do not use the certificate Common Name as a fallback identity.
- Apply the current service-identity rules in RFC 9525.

### 5.2 Client / peer identity

RFC 9525 explicitly places client/end-user identity outside its scope. Therefore, it must **not** be cited as if it standardizes OBIS client-certificate identity.

The OBIS security profile must separately define:
- Which certificate SAN form carries the OBIS peer identifier.
- The exact accepted URI scheme and canonicalization rules if URI SAN is selected.
- Whether one certificate maps to exactly one peer identifier.
- How certificate identity maps to an OBIS peer record and allowed principals.
- How key rotation, multiple active certificates, and identity migration are handled.
- How a valid certificate is still denied when the peer, principal, capability, or scope is not locally authorized.

The X.509 URI SAN field is standardized by RFC 5280, but the OBIS application-specific mapping and authorization semantics must be specified by OBIS itself.

### 5.3 Certificate profile

Before production, specify and test:
- X.509 version and required extensions.
- Basic Constraints and CA/leaf separation.
- Key Usage and Extended Key Usage for server and client authentication.
- SAN requirements and forbidden ambiguous identity sources.
- Maximum certificate validity and accepted clock skew.
- Name/path constraints where used.
- Signature algorithm and key-size policy based on the supported TLS implementation and deployment requirements.
- Certificate chain construction and trust-anchor selection.
- Unknown critical extension behavior.

No custom certificate format or custom cryptographic primitive is permitted.

## 6. Revocation and offline operation

A live OCSP/CRL lookup on every request is not automatically suitable for independent or intermittently connected peers. TLS operational guidance notes that revocation mechanisms can depend on reliable network connectivity.

The final profile must select and test a bounded revocation strategy. Candidates include:
- Owner-distributed, signed trust/revocation bundles with explicit expiry.
- Short-lived leaf certificates plus owner-controlled emergency denylisting.
- OCSP/CRL where the deployment has reliable connectivity and a documented failure policy.

Required invariant: stale or expired revocation state must not silently become "good". The profile must define maximum acceptable staleness, refresh responsibility, fail-closed behavior for consequential operations, and emergency trust-anchor replacement. No online status service is mandatory for every OBIS deployment.

## 7. TLS and application-layer requirements

The production profile should specify, at minimum:

- TLS 1.3 only for the first production binding; no silent downgrade.
- A maintained TLS implementation and supported version matrix.
- Mutual certificate authentication when the profile requires both peers to authenticate.
- Explicit ALPN/application protocol identifier for the OBIS HTTPS binding.
- Certificate verification enabled on both sides; no insecure mode or verify-disabled fallback.
- Explicit handshake and request timeouts, bounded message size, concurrency, and rate limits.
- No secrets in URLs, error bodies, or ordinary logs.
- Peer/principal/capability authorization after authentication and on every request.
- The authenticated peer identity must match the OBIS sender/recipient fields.
- A valid TLS session never grants capability permission by itself.

TLS channel authentication is not a portable detached signature and does not provide non-repudiation for stored evidence. If durable signed evidence is required, define a separate reviewed signature/canonicalization profile.

## 8. Required conformance and security tests

### Certificate validation
- Valid trusted server and client chains.
- Untrusted root, unknown issuer, expired, not-yet-valid, malformed, and revoked certificates.
- Wrong SAN, missing SAN, CN-only certificate, wrong EKU, wrong Key Usage, invalid CA constraints.
- Certificate identity mapped to a different OBIS peer.
- Multiple SAN values and duplicate/ambiguous peer identities.
- Trust-bundle expiry and stale revocation state.
- Certificate rotation overlap, emergency revocation, and trust-anchor replacement.

### TLS behavior
- TLS 1.3 succeeds.
- TLS 1.2 and lower are rejected by the production profile.
- Missing client certificate is rejected where mTLS is required.
- Invalid certificate chains fail closed.
- No plaintext HTTP fallback.
- No invalid ALPN or protocol downgrade.
- Bounded handshake timeout and connection/resource exhaustion tests.

### OBIS authorization
- Authenticated but unregistered peer is denied.
- Authenticated peer with an unapproved principal is denied.
- Valid certificate with insufficient scope is denied.
- Sender/recipient mismatch is rejected.
- Revoked or expired credentials cannot invoke a capability.
- Authorization is re-evaluated for each request.

### Cross-implementation
- Python and Go implementations pass the same test vectors.
- Both reject the same malformed certificates, identity mismatches, downgrade attempts, duplicate/ambiguous fields, and unauthorized capabilities.
- Two peers communicate directly with TRADIX and BRIDEX unavailable.
- Trust and configuration can be exported and restored without a central service.

## 9. Decision gates

Do not mark `OBIS-TLS-MTLS-1` production-approved until:

1. The owner approves the trust model and certificate identity mapping.
2. The profile's normative certificate and TLS requirements are written into the specification.
3. The threat model is updated for the selected profile and revocation strategy.
4. Python and Go implementations pass the shared test suite.
5. Certificate issuance, rotation, revocation, backup, and emergency response are documented.
6. An independent security review finds no unresolved critical/high issue.
7. The owner approves production deployment separately.

## 10. References

- [RFC 8446 — TLS 1.3](https://www.rfc-editor.org/rfc/rfc8446.html)
- [RFC 5280 — Internet X.509 Public Key Infrastructure Certificate and CRL Profile](https://www.rfc-editor.org/rfc/rfc5280.html)
- [RFC 9525 — Service Identity in TLS](https://www.rfc-editor.org/rfc/rfc9525.html) — server service identity; client identity is out of scope.
- [RFC 9325 — Recommendations for Secure Use of TLS and DTLS](https://www.rfc-editor.org/rfc/rfc9325.html)
- [Python ssl module](https://docs.python.org/3/library/ssl.html)
- [Go crypto/tls](https://pkg.go.dev/crypto/tls) and [crypto/x509](https://pkg.go.dev/crypto/x509)
- [OpenSSL licensing](https://www.openssl.org/source/license.html)
- [Rustls](https://github.com/rustls/rustls)
- [Smallstep step-ca](https://github.com/smallstep/certificates)

**Conclusion:** Reuse maintained TLS/X.509 stacks. Keep trust, certificate lifecycle, and OBIS peer authorization owner-controlled. The proposed profile remains a candidate until its client identity mapping, revocation behavior, interoperability evidence, and independent review are complete.
