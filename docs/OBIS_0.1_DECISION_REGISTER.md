# OBIS 0.1 — Decision Register and 1.0 Recommendations

**Status:** Engineering recommendations for owner review; not a normative amendment  
**Applies to:** OBIS draft 0.1.0 and the standalone reference implementation  
**Rule:** No item below becomes a mandatory 1.0 requirement until its security, interoperability, and portability evidence is reviewed and the specification is amended.

This register turns the open questions in the OBIS specification and threat model into explicit decisions, candidate defaults, consequences, and evidence gates. It avoids leaving implementers to invent incompatible defaults.

## 1. Identifier scheme

**Recommendation**

- Represent peer and Bridge instance identifiers as absolute URI strings.
- For locally generated stable instance identifiers, use `urn:uuid:<UUID>` with UUIDv4 generation.
- Keep peer identity, Bridge instance identity, principal identity, and capability identifier as separate fields and concepts.
- Capability identifiers should use an owner-controlled URI namespace. A URI or UUID is an identifier only; it is never proof of identity, ownership, trust, or permission.
- Do not require a central registry, global discovery service, or TRADIX/BRIDEX naming service.

**Reasoning**

UUID-based instance IDs avoid dependence on a domain name, registry operator, or ecosystem namespace. Owner-controlled capability namespaces permit readable identifiers while keeping namespace administration local.

**Evidence gate**

Two independently administered implementations must exchange identifiers without a shared registry. Tests must cover duplicate identifiers, malformed URIs, identity substitution, and owner migration.

## 2. Schema dialect and canonical layout

**Draft baseline selected for the 0.1 artifact**

- JSON Schema Draft 2020-12.
- Canonical standard artifact: `standards/obis/0.1/message.schema.json`.
- The standalone Python package carries an identical packaged copy; CI verifies byte-for-byte equality.
- Envelope schemas are strict. Domain payload schemas are separately versioned and referenced by capability contracts.
- A schema URI is a stable identifier, not a requirement to fetch schemas from a live network service.

**Remaining work**

Runtime schema-driven validation, schema negotiation, payload-schema registry format, and multi-language schema conformance remain open. The reference implementation currently performs strict hand-coded envelope checks and tests the published JSON Schema artifact separately.

## 3. Initial production security profile candidate

**Candidate name:** `OBIS-TLS-MTLS-1`

The candidate profile should require:

- HTTPS with TLS 1.3; plaintext HTTP is prohibited outside loopback development tests.
- Mutual TLS with X.509 certificates for peer authentication.
- A profile-defined peer identity in the certificate Subject Alternative Name, explicitly mapped to the configured OBIS peer identifier. URI SAN is a candidate, but its exact scheme, canonicalization, and one-certificate-to-one-peer rules must be defined by OBIS.
- Owner-controlled trust anchors and peer authorization configuration. A central certificate authority or identity provider is not mandatory.
- Separate authentication and authorization checks. A valid certificate never grants capability access by itself.
- Documented certificate issuance, expiry, rotation, revocation, trust-bundle replacement, and incident response.
- No custom cryptographic protocol or custom TLS implementation.

**Why this is a candidate, not an approval**

TLS 1.3 and X.509 are mature standards, but selecting them does not by itself settle trust-anchor operations, certificate-to-peer mapping, revocation behavior, deployment profiles, or implementation security. These must be reviewed against the threat model and tested across at least two independent implementations before production approval.

The development HMAC profile in the Python prototype is not an alternative production profile and must never be used for real network deployments.

## 3A. Certificate identity scope correction

RFC 9525 specifies service identity verification for TLS and explicitly places client/end-user identity outside its scope. It must not be treated as the normative definition of OBIS client-certificate identity. RFC 5280 defines the X.509 URI SAN field, but OBIS must define the application-specific mapping from that field to a peer identity, principal, and local authorization record.

The server endpoint identity and the authenticated client/peer identity are separate checks. A valid client certificate authenticates a certificate holder only under the selected trust model; it does not authorize any OBIS capability.

The implementation choices, certificate-profile requirements, revocation candidates, and test gates are recorded in [OBIS Production Security Profile Implementation Audit](OBIS_SECURITY_PROFILE_IMPLEMENTATION_AUDIT.md). The audit is a recommendation, not production approval.

## 4. Transport binding

**Recommendation**

Define HTTPS/TLS 1.3 as the first production transport-binding candidate, separately from the OBIS core envelope. For the current HTTP binding, negotiate HTTP/1.1 ALPN; OBIS versioning remains in the message envelope and media type. Keep transports replaceable and do not require a relay, broker, or shared gateway.

The current loopback HTTP binding exists only to make the reference tests deterministic and safe to run locally. It is not the production transport binding.

## 5. Message signing and canonicalization

**Recommendation**

- Use transport security for live channel confidentiality and integrity.
- Do not claim transport authentication provides portable signed evidence or non-repudiation.
- If detached message/evidence signatures are required, evaluate JSON Canonicalization Scheme (JCS, RFC 8785) as the canonical JSON representation.
- Select signature algorithms, key ownership, timestamping, verification, and revocation only in a separate reviewed security profile.
- Do not invent a custom canonicalization algorithm.

**Evidence gate**

Independent implementations must produce identical canonical bytes for the same supported JSON values and verify valid signatures while rejecting altered payloads, changed recipients, duplicate/ambiguous fields, and invalid key bindings.

## 6. Asynchronous operation lifecycle

**Recommended common lifecycle**

`accepted → running → completed | failed | cancelled | expired`

Each asynchronous operation should expose:

- A unique operation reference scoped to the receiving peer and caller.
- An explicit expiry/deadline.
- A status capability and, where supported, a cancellation capability.
- A stable terminal outcome and structured error.
- An idempotency key for every retryable operation that can cause side effects.
- Owner-defined retention and reconciliation behavior.

A cancellation request is not proof that an external side effect was rolled back. The operation contract must state whether cancellation is best-effort, transactional, or unsupported.

## 7. Compatibility and deprecation

**Recommendation for discussion**

- Keep the existing MAJOR.MINOR protocol version model.
- Breaking envelope or semantic changes require a new MAJOR version.
- Additive, backward-compatible capabilities may use MINOR increments.
- Publish explicit support windows. Candidate minimum: the current and immediately preceding minor version, with at least 12 months' notice before deprecation, whichever gives the longer support period.
- No silent downgrade to weaker security, narrower semantics, or broader permissions.

The support window is a governance choice and must be agreed by independent implementers before 1.0.

## 8. Governance and stewardship

**Recommendation**

- Publish the normative specification, schemas, test vectors, conformance tests, and migration notes in an exportable public repository.
- Keep the standard usable without BRIDEX or TRADIX services.
- Permit multiple independent implementations and test harnesses.
- Use public versioned change proposals with compatibility and security review.
- No exclusive certification, mandatory registry, mandatory relay, or proprietary conformance dependency.
- Define a succession process so stewardship can move to another independent maintainer group.

The long-term steward and approval process remain unresolved.

## 9. Required evidence before OBIS 1.0

1. Owner review of the identifier and compatibility recommendations.
2. Security review and threat-model update for the first production profile.
3. TLS 1.3 mutual-authentication candidate implemented in Python and Go without custom cryptography.
4. Certificate-to-peer identity and fingerprint mapping tests are present; certificate issuance, rotation, durable revocation, trust-bundle freshness, and emergency denylisting remain open.
5. Normative request, success-response, error-response, and capability payload schemas.
6. Runtime schema validation and schema-version negotiation tests.
7. Durable replay protection and idempotency/outcome reconciliation.
8. Async lifecycle conformance tests, including cancellation races and expiry.
9. A second implementation in a different language maintained independently of the Python reference.
10. Cross-implementation positive, negative, malformed-input, downgrade, and portability tests.
11. Clean-environment proof that two peers communicate with TRADIX and BRIDEX unavailable.
12. Independent security review; local CI success is not a substitute.

## 10. Current implementation boundary

The Python and Go reference peers are independently buildable development/conformance prototypes. Both implement the draft envelope and a loopback-only HMAC development profile. Their TLS 1.3 mTLS candidate uses no HMAC secret, binds a canonical URI SAN and certificate SHA-256 fingerprint to a local credential/principal, and validates the remote peer identity before accepting a connection. Bidirectional Python/Go loopback mTLS tests and a wrong-fingerprint rejection test are included in the current implementation branch.

The candidate is not production-approved. Durable replay/idempotency, durable revocation, trust-bundle freshness, certificate lifecycle, production audit, asynchronous operations, expanded cross-language conformance, and independent security review remain open. See [OBIS Reference Implementation Status](../projects/BRIDEX/reference/OBIS_REFERENCE_IMPLEMENTATION_STATUS.md).

**No production or 1.0 claim is authorized by this register.**


## 12. Current implementation status (2026-11-20)

- OBIS 0.1 specification and schema remain draft baselines.
- The Python reference and independent Go reference are development/conformance prototypes; their HTTP/HMAC mode is loopback-only and is not a production security profile.
- The earlier Draft PR #76 failed Go compilation due to an unused import and is not the accepted implementation line. The corrected ordered implementation is Draft PR #78, stacked on PR #77. Its latest code-tested head `89113c33aa12b71cc59dfe072773b92368955bf7` passed OBIS conformance run `44743858735` (57 Python tests, Go tests, wheel build/install, schema parity, and independence checks). Repository run `44743120802` passed 104 TRADIX tests, and the BRIDEX Engine dependency passed 27 tests in run `44742859047`. These runs validate the loopback candidate only, not production security.
- Certificate issuance, rotation, revocation, trust-bundle freshness, emergency denylisting, durable replay/idempotency, production audit, and independent security review remain open.
- No production endpoint, credential, live peer, deployment, or external connection is authorized by this status record.
