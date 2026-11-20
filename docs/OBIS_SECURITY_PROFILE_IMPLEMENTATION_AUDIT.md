# OBIS — Production Security Profile Implementation Audit

**Document ID:** OBIS-SEC-AUDIT-001  
**Status:** Evidence-based implementation audit and design recommendation; owner/security review required  
**Target:** OBIS-TLS-MTLS-1 candidate  
**Applies to:** OBIS 0.1 development and future production profile work  
**Decision authority:** Bridge owner and independent OBIS security reviewers

## 1. Purpose and decision boundary

This audit evaluates whether OBIS should implement transport security and certificate handling itself or reuse maintained TLS/X.509 implementations.

**Decision:** Do not implement cryptographic primitives, TLS, certificate-path validation, or a custom PKI. Reuse the platform's maintained TLS stack. Keep peer authorization, capability scopes, and OBIS identity-to-certificate binding in the OBIS application layer.

This audit does not approve a production security profile, select a final certificate lifecycle, or authorize internet-facing deployment. The current Python HMAC/loopback prototype remains development-only.

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
- Add a separate TLS integration mode only after the certificate profile and test fixtures are reviewed.
- Keep certificate loading, trust configuration, and private-key paths owner-supplied. Never commit test or production private keys.

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

## 10. Go client validation of signed errors from the Python peer — 2026-11-20

The cross-language Python integration harness now explicitly checks two authenticated failure paths received by the independent Go client:

- **Authorization denial:** the Python peer has a registered `records.read` capability, but the Go request does not carry the required scope. The Go client must validate the signed failed response and report `authorization.denied`; the registered capability handler's invocation counter must remain empty.
- **Unknown capability:** the Python peer registers `records.read`, while the Go client requests `missing.capability`. The Go client must validate the signed failed response and report `capability.unknown`; the registered handler's invocation counter must remain empty.

For both cases, the Go `Invoke` path verifies the response HMAC before validating the failed-response envelope, including the request correlation ID and expected remote/local peer identities. The tests assert the surfaced error code and prove that no registered capability handler ran.

This is selected Go-client-to-Python-peer authenticated error coverage. It does not replace the separate Go unit tests for rejection of invalid signatures, mismatched correlation IDs, and wrong peer identities; nor does it establish the complete bidirectional negative conformance matrix. HMAC remains development/conformance-only. Production TLS/mTLS, credential lifecycle, independent security review, and full OBIS conformance remain open.

## 11. References

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


## 12. Go client rejection of invalid authenticated error responses — 2026-11-20

The independent Go client test suite now verifies that an HTTP error response is not trusted merely because it has the expected error status or shape. Using locally generated HMAC-signed error envelopes, the tests confirm that Invoke rejects:

- An error response with an invalid HMAC signature.
- A correctly signed error response with a mismatched correlation ID.
- A correctly signed error response claiming the wrong sender peer identity.
- A correctly signed error response claiming the wrong recipient peer identity.

These checks complement the existing Go client tests for downgraded successful responses, wrong correlation/sender identity, unexpected fields, and malformed signed error objects. The tests exercise the client validation boundary independently of the Python integration harness.

CI run #1199 passed on consolidated PR #42 head 02270e2bd44d704718e3ef033c6be9d6c125b741 (run ID 44765422084). The run completed Go tests and binary build, the configured Python/BRIDEX Core/OBIS/ECOSCAN test suites, and isolated wheel build/install/schema checks for all three Python packages.

This closes the listed Go-client rejection tests for invalid signatures and mismatched error-response correlation/peer identities. It does not establish full bidirectional negative conformance, production TLS/mTLS, credential lifecycle, distributed replay protection, durable business-operation idempotency, persistent audit/evidence, or independent security approval. HMAC remains development/conformance-only. No normative OBIS/TIIS contract, schema, or version-negotiation semantics changed.


## 13. OBIS 0.2 implementation gap review — 2026-11-20

This review is based on the current PR #42 head `9fb0c071de4e9da08088c5bba7bd788fcef6a694` and current PR #67 head `fcbfac0a3a0c546d78622ec8e0aaca252593b2a1`. Both pull requests remain open, Draft, and unmerged.

### 13.1 Version parity is not complete

- Python has a separate executable OBIS 0.2 peer, loopback HTTP server/client, RFC 8785 request projection hashing, durable operation-ledger integration, duplicate-operation result recovery, and authenticated status lookup.
- Go currently has the durable file-backed Operation Ledger as a storage primitive, but its `peer.go`, `client.go`, HTTP route, and CLI remain OBIS 0.1. The Go ledger is not wired into a Go 0.2 peer or client.
- Go `CanonicalJSON` is a development serializer, not RFC 8785 JCS. It MUST NOT be used for OBIS 0.2 request hashes. Go JCS dependency selection and cross-language byte-for-byte validation remain open.
- The existing Python↔Go tests exercise OBIS 0.1. They do not establish OBIS 0.2 cross-language conformance.
- No shared OBIS 0.2 JCS conformance-vector suite is currently demonstrated by the reviewed files.

### 13.2 ECOSCAN wire-test scope

PR #67 contains an actual loopback HTTP test between the ECOSCAN adapter and an independent BRIDEX Python reference peer. It verifies the 0.1 signed request/response path, inventory capability mapping, project/source grant rejection, and peer identity checks. It is not a Go-peer test and does not exercise OBIS 0.2 operation identity, idempotency, status recovery, or Go/Python 0.2 interoperability.

The next integration gate must therefore add a separate ECOSCAN-to-independent-Go-peer loopback test after Go 0.2 is implemented. It must prove that the test peer is a separately started process, that ECOSCAN sends the 0.2 operation request, that the peer enforces its own project/source grant before invoking the provider callback, and that status/result recovery does not execute the callback twice. The test must remain synthetic and loopback-only.

### 13.3 Newly identified Python 0.2 error-response gap

The reviewed Python 0.2 HTTP handler signs successful operation responses, but its exception path currently returns a minimal unsigned error object. This is weaker than the authenticated correlated error-response behavior tested for the 0.1 reference implementation. Before declaring 0.2 cross-language parity, define and implement a versioned 0.2 error envelope with:
- authenticated response signature when the request identity has been authenticated;
- request correlation ID and explicit sender/recipient peer IDs;
- stable error code and safe message;
- strict client-side validation of status, content type, envelope, signature, correlation, and peer identity;
- no signed identity disclosure for unauthenticated or malformed requests.

Add positive and negative tests for authentication failure, authorization denial, unknown capability, request-hash mismatch, idempotency conflict, ledger unavailable, replay, expired request, and malformed response. Ensure no provider callback runs for pre-execution rejection cases.

### 13.4 Operation lifecycle and crash boundaries

The Go ledger is a persistence primitive only. Go Peer integration must reserve before execution, persist RUNNING before invoking the handler, persist SUCCEEDED together with exactly one result representation, and recover stale RUNNING records to UNKNOWN before serving requests. Duplicate operation requests must return the existing record and must not invoke the handler again.

The Go ledger uses a lock directory and deliberately fails closed on a stale lock. This avoids unsafe automatic lock removal but creates an operator-recovery requirement. File replacement and directory fsync semantics must be tested on each supported operating system; the existing Linux CI result does not establish Windows portability or power-loss durability.

The Python 0.2 handler currently transitions an operation to RUNNING before invoking the capability. Its handler-exception path conservatively records UNKNOWN. Tests must additionally cover process termination at each persistence boundary, ledger write failures, concurrent duplicate requests, and response loss after a committed result.

### 13.5 HTTP server resource controls

The reviewed Go 0.1 HTTP handler enforces a body-size limit and rejects transfer encoding, but its reference server does not itself configure bounded header-read, body-read, idle, and write timeouts, connection/concurrency limits, or a request-rate policy. The Python 0.2 ThreadingHTTPServer similarly needs explicit bounded request/header/body timeouts and concurrency/resource controls. These are development-server gaps to close or explicitly constrain in the reference test harness; they are not production security controls.

### 13.6 Required implementation order

1. Select and pin a maintained, permissively licensed Go RFC 8785 implementation; record its exact module version, license, provenance, and API. Do not substitute Go's standard JSON encoder for JCS.
2. Add shared JCS vectors consumed unchanged by Python and Go, including Unicode property ordering, escaping, number serialization, nested structures, invalid I-JSON values, and request-hash projection.
3. Implement a separate Go OBIS 0.2 peer/HTTP route using the existing owner-local ledger; preserve OBIS 0.1 behavior and route unchanged.
4. Implement the Go 0.2 client with stable operation ID/idempotency key, per-attempt message/nonce/attempt IDs, authenticated status query, response signature and identity validation, and conservative UNKNOWN transport classification.
5. Define and test the signed 0.2 error response contract on both implementations.
6. Run bidirectional Python↔Go 0.2 positive, negative, duplicate-delivery, restart-recovery, and status-query tests.
7. Run ECOSCAN against a separately started independent Go 0.2 peer over loopback, with synthetic provider callback and project/source isolation assertions.
8. Add separate capability fixtures for BRIDEX-owned and TRADIX-owned engineering peers. Keep the owners, credentials, ledgers, and capability grants distinct; do not route either through a central BRIDEX/TRADIX runtime.
9. Re-run security review and record unresolved gaps before any non-loopback or production proposal.

### 13.7 Current production decision

OBIS 0.2 is not yet cross-language executable or production-approved. The current reference transports use loopback HTTP and shared-secret HMAC for development/conformance only. No TLS/mTLS production profile, certificate-to-peer identity binding, trust-anchor lifecycle, revocation mechanism, independent security review, or production credential lifecycle is complete. No live provider connection, deployment, or production pilot is authorized by this review.

PR #42 and PR #67 remain Draft and unmerged. This review makes no change to MegaMarket or NEXORA and authorizes no merge, deployment, or live external connection.


## 14. Go RFC 8785 canonicalization integration started — 2026-11-20

- Added a dedicated Go JCS boundary in `projects/BRIDEX/reference/obis-go/obis/jcs.go`, using the Go implementation listed in RFC 8785 Appendix G: `github.com/cyberphone/json-canonicalization/go`.
- Pinned module version: `v0.0.0-20241213102144-19d51d7fe467`; pkg.go.dev reports Apache-2.0 licensing and publication on 2024-12-13.
- The wrapper rejects duplicate JSON object keys before canonicalization and checks that canonicalizer output is valid JSON.
- Added Go tests for the RFC 8785 Appendix B sample, duplicate keys, scalar top-level rejection, and Unicode property ordering.
- The JCS wrapper is intentionally separate from the existing OBIS 0.1 HMAC serializer. It has not yet been wired into OBIS 0.2 operation request hashing.
- **Validation pending:** no CI result has been observed for the commits adding this dependency and test. The import path, module resolution, exact vector bytes, and test behavior must be confirmed by CI before treating the integration as validated.
- This is not Go OBIS 0.2 Peer/Client implementation and does not establish cross-language conformance.

Reference: RFC 8785 Appendix G lists the cyberphone Go implementation as JCS-compatible; the module's package documentation identifies its Transform API and Apache-2.0 license.


## 15. OBIS 0.2 implementation and loopback validation update — 2026-11-20

This section supersedes the earlier “not yet cross-language executable” status in §13.7 and the validation-pending status in §14. It records the current reference implementation state; it does not approve production use.

### Implemented and CI-tested

- Go JCS is pinned to `github.com/cyberphone/json-canonicalization` at `v0.0.0-20241213102144-19d51d7fe467`; `go.sum` is committed. The Go JCS wrapper rejects duplicate keys and is used by the OBIS 0.2 request-hash projection.
- Go `OperationRequestHash` hashes the protocol-defined request projection, not the transport envelope.
- Go `PeerV02`, `ClientV02`, and `/obis/v0.2/messages` are implemented alongside the unchanged 0.1 route.
- The Go peer reserves operations in its owner-local file ledger, records RUNNING before invoking the handler, persists terminal results, and recovers interrupted RUNNING records as UNKNOWN.
- Idempotent duplicate delivery returns the prior operation record without invoking the handler again. Status queries verify operation identity and, for resource-bound capabilities, the original project/source identity stored in the ledger.
- Credentials carry explicit scopes and resource grants. Resource-bound capability authorization is checked before handler execution.
- The Go development HTTP server binds to loopback and configures bounded header/read/write/idle timeouts and header/body size limits. This is a local conformance harness, not a production server profile.
- Bidirectional Python↔Go OBIS 0.2 loopback tests cover request/response signing, operation results, duplicate delivery, status lookup, and resource-bound authorization.
- A separate-process ECOSCAN integration test starts the Go peer on loopback, uses a synthetic inventory capability, and verifies that only a committed SUCCEEDED result becomes ECOSCAN measurements. UNKNOWN/RUNNING/ACCEPTED outcomes are not converted into measurements.
- Separate BRIDEX and TRADIX owner fixtures use distinct peer identities, credentials, scopes, resource grants, and operation ledgers. Tests reject cross-owner credentials and cross-project resource access.

### Validation evidence

- PR #42 Go/Python test workflow passed on commit `edd3d3f96fb6c6db46c1915dc783939b4574b762`, workflow run `44806996730`. A newer PR #42 head was still under CI review when this audit update was prepared.
- PR #67 standalone ECOSCAN workflow and repository test workflow passed on commit `17d3416d2e2ede583817c84fb7617eb009d85312`, runs `44806912276` and `44806912157`. The workflow checks out a pinned OBIS reference commit, builds the Go peer for tests, and does not add it as an ECOSCAN runtime dependency.
- Both PRs remain Draft and unmerged. Passing CI is not a merge, deployment, provider connection, or production approval.

### Remaining blockers and limits

1. OBIS 0.2 error responses are not yet signed correlated error envelopes. Successful responses are signed and checked; HTTP/protocol rejection paths still return unsigned errors. Define and test the authenticated error contract before relying on remote error details.
2. Production TLS/mTLS, certificate-to-peer identity binding, trust-anchor management, rotation/revocation, and production credential lifecycle are not implemented.
3. The Go server has no explicit concurrency cap or rate limiter. The Python threaded server also needs bounded concurrency and request-resource controls.
4. The capability recovery class is registered as metadata; a complete policy engine for IDEMPOTENT, QUERYABLE, and NON_RECOVERABLE recovery behavior is still required. UNKNOWN remains fail-closed.
5. Crash/power-loss durability and stale-lock operator recovery need broader platform testing. Linux CI does not prove Windows behavior or power-loss guarantees.
6. Independent security review and production threat-model review remain outstanding.

No live provider, non-loopback peer, deployment, or production pilot was used or authorized. MegaMarket and NEXORA remain untouched.
