# OBIS — Open Bridge Interoperability Standard

**Document ID:** OBIS-SPEC-001  
**Status:** Draft specification / architecture baseline  
**Version:** 0.1.0  
**Protocol family:** OBIS  
**Effective date:** 2026-11-20  
**Stewardship:** BRIDEX may maintain reference material and conformance tooling; the specification must remain independently usable and must not be controlled by a mandatory BRIDEX/TRADIX service.  
**Normative language:** The terms MUST, MUST NOT, REQUIRED, SHOULD, SHOULD NOT, and MAY are to be interpreted as normative requirements.

## 1. Purpose and design objective

OBIS defines a vendor-neutral, independently implementable interoperability contract for communication between independently owned tools, services, platforms, and Bridge instances.

OBIS exists so that a Bridge remains useful when its owner leaves TRADIX, stops using BRIDEX, changes its infrastructure, changes its operator, or connects to a different ecosystem.

OBIS is a protocol specification, not a central service, hosted network, product registry, broker, identity provider, or mandatory runtime. Implementations may be developed by different parties and must interoperate using this published contract.

## 2. Scope and non-goals

OBIS specifies:
- Peer and Bridge identity references.
- Protocol negotiation and compatibility.
- Capability description and negotiation.
- Message envelope and request/response correlation.
- Authentication context and authorization boundaries.
- Data classification and disclosure constraints.
- Error categories and reliability semantics.
- Audit/evidence references and operational lifecycle signals.
- Conformance requirements and extension rules.

OBIS does not prescribe:
- A single hosting provider, cloud, repository, deployment platform, or network topology.
- A mandatory central discovery service, relay, broker, registry, or identity provider.
- A single authentication product or credential vendor.
- Business-domain semantics for every product.
- Permission to access a peer merely because it is discoverable or has completed a handshake.
- Automatic compatibility with every third-party system.

## 3. Core principles

1. **Independent operation:** An OBIS implementation MUST operate without TRADIX or BRIDEX runtime services.
2. **Owner control:** The designated Bridge owner controls deployment, peer configuration, credentials, scopes, data sharing, and lifecycle.
3. **No implicit trust:** Network reachability, portfolio membership, catalog presence, and handshake success MUST NOT grant authorization.
4. **Least privilege:** Every operation and data disclosure MUST be explicitly scoped.
5. **Replaceable transport:** OBIS semantics MUST remain separate from transport-specific details.
6. **Open implementation:** A conforming implementation MUST be possible from this specification and its published schemas without proprietary BRIDEX assets.
7. **Direct-capable communication:** Peers SHOULD communicate directly where feasible. Intermediaries MAY be used when explicitly configured and trusted, but no BRIDEX/TRADIX intermediary is mandatory.
8. **Local autonomy:** A peer remains responsible for its own interface, exposed capabilities, data, and authorization decisions.
9. **Portability:** A Bridge owner MUST be able to move the implementation, source, configuration, and operation to another environment or maintainer.
10. **Minimal stable core:** Domain-specific behavior belongs in declared extensions, not in the base protocol.

## 4. Terminology and identities

- **Peer:** An independently administered system participating in an OBIS exchange.
- **Bridge:** An independently deployable tool that mediates approved interactions between peers.
- **Bridge owner:** The explicitly designated entity with ownership and control rights for a Bridge instance.
- **Operator:** The entity running the Bridge. It may differ from the owner.
- **Maintainer:** The entity responsible for source changes and releases. It may differ from owner and operator.
- **Capability:** A named, versioned operation or service a peer declares it can provide.
- **Profile:** A declared set of optional protocol features or constraints.
- **Extension:** A separately versioned addition to OBIS for a domain, transport, or security mechanism.

Each peer and Bridge MUST have a stable identifier within its declared administrative namespace. Identifiers MUST be opaque and MUST NOT be interpreted as proof of ownership, trust, or permission. Implementations MAY use URI-based identifiers, UUIDs, or another documented globally collision-resistant scheme. Identifier format and namespace MUST be declared in the peer's identity metadata.

Identity of a peer, identity of a Bridge, and identity of a human/service principal MUST remain distinguishable. A Bridge MUST NOT impersonate its peer or its owner.

## 5. Protocol layers

OBIS is divided into independently versioned layers:

1. **Core semantics:** identity references, negotiation, capability model, envelope, errors, and lifecycle semantics.
2. **Security profile:** authentication method, credential binding, authorization context, replay protection, and key/credential lifecycle.
3. **Transport binding:** mapping OBIS messages to a transport such as HTTPS, message queue, or another explicitly specified channel.
4. **Payload format/profile:** serialization and domain schema constraints.
5. **Domain extension:** optional domain-specific capabilities and schemas.

A transport binding MUST NOT silently redefine core authorization, identity, or error semantics. A domain extension MUST NOT weaken the base security requirements.

## 6. Versioning and compatibility

The protocol identifier is `obis`. A protocol version uses `MAJOR.MINOR` numeric form.

- A MAJOR change may be incompatible and requires explicit negotiation.
- A MINOR change may add backward-compatible optional fields, capabilities, or behavior.
- Unknown optional fields MUST be safely ignored where the relevant schema permits.
- Unknown required features MUST cause explicit rejection, not silent downgrade.
- A peer MUST declare the exact supported versions and required profiles.
- A sender MUST NOT assume that the highest version it supports is supported by the recipient.
- Breaking changes MUST NOT be introduced under an unchanged MAJOR version.
- Deprecation MUST include a published replacement and a stated support window.

Version negotiation MUST select a mutually supported version and profile. If no safe common version exists, the connection or operation MUST fail with a stable compatibility error. Silent fallback to weaker authentication or broader permissions is prohibited.

## 7. Peer establishment and handshake

The handshake establishes protocol compatibility and authenticated peer context. It does not grant access to capabilities or data.

A conforming implementation MUST support the following logical sequence:

1. **Local policy check:** The receiving peer checks whether the remote peer is configured or whether a declared enrollment process is allowed.
2. **Protocol offer:** The initiating peer declares identity references, supported OBIS versions, supported security profiles, transport binding, and implementation metadata.
3. **Authentication:** Both sides authenticate according to a mutually accepted security profile. Mutual authentication SHOULD be used for consequential or sensitive operations.
4. **Negotiation:** The peers select a compatible version, security profile, transport binding, and optional features.
5. **Capability exchange:** Each side may declare capabilities and schemas it is willing to expose to that specific peer.
6. **Authorization:** Each side independently evaluates which capabilities, fields, and actions the remote principal may use.
7. **Session/context establishment:** The peers establish bounded session or request context, expiry, and revocation behavior.

The handshake MUST NOT:
- Automatically trust a newly discovered peer.
- Grant all declared capabilities.
- Expand scopes beyond local policy.
- Expose secrets or unrestricted internal metadata.
- Disable certificate, credential, or principal validation to achieve compatibility.

Implementations MUST provide a way to revoke a peer relationship and terminate or reject requests from a revoked peer.

## 8. Capability model

A capability declaration MUST include:
- Stable capability identifier.
- Human-readable name and purpose.
- Capability version.
- Input and output schema references and versions.
- Required authorization scope(s).
- Data classification and disclosure notes.
- Side-effect classification: read-only, state-changing, financial/irreversible, or other declared class.
- Idempotency support and required key behavior, where relevant.
- Timeout and payload bounds.
- Deprecation/support status.

Capability discovery is descriptive only. It is not authorization. A peer MUST authorize every invocation independently or through an explicitly bounded authorization grant.

Capabilities MUST be narrow and typed. Generic shell execution, arbitrary code execution, unrestricted filesystem access, unrestricted database access, and unrestricted network proxying MUST NOT be exposed as base OBIS capabilities.

## 9. Message envelope

The base OBIS message representation uses UTF-8 JSON. Alternative encodings require a separately declared profile. The following is an illustrative structural example, not a complete schema:

```json
{
  "protocol": "obis",
  "version": "0.1",
  "message_type": "request",
  "message_id": "msg-unique-value",
  "correlation_id": "optional-parent-or-trace-id",
  "sender": {
    "peer_id": "peer:example-a",
    "bridge_id": "bridge:example-a-to-b"
  },
  "recipient": {
    "peer_id": "peer:example-b"
  },
  "issued_at": "2026-11-20T10:00:00Z",
  "expires_at": "2026-11-20T10:00:30Z",
  "capability": {
    "id": "example.read-record",
    "version": "1.0"
  },
  "authorization": {
    "principal_ref": "principal:service-a",
    "scopes": ["record:read"]
  },
  "payload": {
    "record_id": "record-123"
  },
  "evidence_ref": "optional-owner-controlled-reference"
}
```

Required envelope fields and their schema constraints MUST be defined in the versioned OBIS schema package. Implementations MUST reject malformed messages, invalid identifiers, unsupported required features, expired messages, oversized payloads, and schema-invalid payloads before executing the requested capability.

A response MUST include the original request's correlation identifier, a unique response message identifier, a normalized outcome, and either a typed result or a structured error. Secrets, access tokens, private keys, and unnecessary personal or business data MUST NOT be placed in the general envelope.

## 10. Authorization and data boundaries

Authentication answers who is communicating. Authorization determines what that principal may do. These checks MUST remain separate.

Every capability invocation MUST be evaluated against:
- Authenticated principal and peer identity.
- Explicit capability identifier and version.
- Granted scope and scope expiry.
- Requested data fields and data classification.
- Local policy of the receiving peer.
- Operation risk and side-effect classification.
- Revocation and freshness status.

Default behavior is deny. Missing, expired, ambiguous, or unverifiable authorization MUST result in rejection.

Each peer controls its own data. OBIS does not transfer ownership of data or authorize secondary use. The parties MUST define permitted purposes, fields, retention, onward disclosure, deletion, and audit obligations in an agreement or policy outside the wire protocol where legally or operationally required.

## 11. Security requirements

Every production OBIS deployment MUST select and document a security profile appropriate to its threat model.

At minimum:
- Authenticate peers using a documented, maintained mechanism.
- Protect message confidentiality and integrity in transit.
- Validate certificate/credential chains and identity bindings where applicable.
- Enforce authorization on the receiving side.
- Apply bounded message sizes, parsing depth, and processing time.
- Validate timestamps, expiry, and replay controls.
- Use unique message identifiers and idempotency keys for retryable state-changing operations.
- Rotate and revoke credentials without rebuilding the protocol implementation.
- Keep secrets outside source code, ordinary configuration exports, logs, and audit payloads.
- Avoid leaking whether protected resources exist when disclosure itself is sensitive.
- Record security-relevant decisions without storing unnecessary sensitive payloads.

The base specification does not mandate a single cryptographic algorithm or identity vendor. Concrete production profiles MUST specify algorithms, key sizes, trust anchors, rotation, revocation, and downgrade protections. An implementation MUST NOT claim production security conformance by merely declaring that it uses encryption.

## 12. Request, response, and reliability semantics

A request MUST have a unique message identifier, a bounded expiry/deadline, a declared capability, and a validated payload.

A response MUST be attributable to the request and MUST distinguish:
- Completed successfully.
- Accepted for asynchronous processing.
- Rejected by authentication or authorization.
- Rejected as invalid or unsupported.
- Failed before execution.
- Failed during execution, with side-effect status stated where safely knowable.
- Timed out or outcome unknown.

State-changing operations MUST define idempotency behavior. A retry MUST NOT create duplicate effects when the operation declares idempotency support and a valid idempotency key is reused within the declared retention window.

Implementations MUST define bounded retry rules, exponential backoff where appropriate, cancellation behavior, and maximum execution time. A timeout MUST NOT be interpreted as proof that a remote side effect did not occur. Where outcome is unknown, the caller MUST reconcile using an operation-status or evidence query rather than blindly repeating the action.

Asynchronous operations MUST return an operation reference, expiry, and supported status-query/cancellation behavior. These are capability-specific and must be declared.

## 13. Error model

Errors MUST use stable machine-readable categories and MUST NOT expose secrets, stack traces, internal paths, or sensitive implementation details to remote peers.

The base categories are:
- `protocol.invalid_message`
- `protocol.unsupported_version`
- `protocol.unsupported_feature`
- `identity.unknown_peer`
- `identity.authentication_failed`
- `authorization.denied`
- `authorization.expired`
- `capability.unknown`
- `capability.unsupported_version`
- `payload.invalid`
- `payload.too_large`
- `request.expired`
- `request.replay_detected`
- `request.idempotency_conflict`
- `operation.timeout`
- `operation.outcome_unknown`
- `operation.failed`
- `rate_limit.exceeded`
- `peer.unavailable`
- `internal.error`

An error response SHOULD include a safe retryability indicator and a correlation reference. It MUST NOT include a raw exception or confidential diagnostic data.

## 14. Audit and evidence

Each implementation MUST produce attributable audit evidence for:
- Peer enrollment, trust changes, and revocation.
- Authentication failures and authorization decisions.
- Capability invocations with principal, capability, outcome, and correlation reference.
- State-changing or consequential operations.
- Configuration, policy, and version changes.
- Export, restore, and lifecycle actions.

Audit records MUST be protected against unauthorized alteration and access. Retention, export, and deletion are controlled by the Bridge owner and applicable law. OBIS does not require a central audit service. Evidence references MUST resolve within an owner-controlled or mutually agreed boundary.

## 15. Health and lifecycle

A conforming implementation MUST provide locally inspectable operational state and document its health semantics.

Where a remote health endpoint is exposed, it MUST disclose only approved operational metadata. At minimum, lifecycle states SHOULD distinguish:
- starting
- ready
- degraded
- draining
- disabled
- stopped

Readiness MUST NOT imply that every capability is authorized or available. A peer MUST be able to disable or revoke a Bridge relationship without depending on BRIDEX/TRADIX.

## 16. Transport bindings and intermediaries

OBIS core semantics are transport-neutral. A transport binding MUST document:
- Addressing and routing.
- Authentication and channel protection.
- Message framing and maximum size.
- Timeout and cancellation mapping.
- Delivery guarantees and duplicate behavior.
- Error mapping.
- Health and connection lifecycle.
- Proxy/intermediary behavior, if any.

A transport intermediary MAY be used when explicitly configured by the relevant owners. It MUST NOT silently change message identity, authorization scope, payload meaning, or audit attribution. A central relay is not a protocol requirement.

## 17. Extensions and profiles

Extensions MUST have:
- A unique namespace and identifier.
- A maintainer and support contact.
- Explicit versioning and compatibility rules.
- Declared required/optional status.
- Security and data-boundary analysis.
- Conformance tests.
- A migration/deprecation policy.

An extension MUST NOT redefine a base field or weaken a mandatory base requirement. Unknown optional extensions may be ignored only where safe; unknown required extensions MUST cause explicit rejection.

## 18. Conformance

An implementation may claim **OBIS Core Conformance** only if it passes the published tests for:
- Message and schema validation.
- Version and feature negotiation.
- Identity separation.
- Capability declaration and negotiation.
- Authentication and authorization separation.
- Default-deny behavior and revocation.
- Expiry, replay, payload bounds, and error handling.
- Request/response correlation and idempotency behavior.
- Audit evidence and safe error disclosure.

A Bridge may claim **OBIS Interoperability Conformance** only after successful cross-implementation tests with:
1. Another independently implemented OBIS peer.
2. A non-TRADIX system or a separately implemented Bridge outside TRADIX.
3. TRADIX and BRIDEX runtime services unavailable.
4. No mandatory central registry, relay, or identity provider.
5. A documented, independently reproducible test environment.

Unit tests or two instances of the same implementation are insufficient by themselves to prove cross-implementation interoperability.

Portability acceptance additionally requires the owner to build and operate the Bridge from its exported source/package and documentation in a separate repository or environment.

## 19. Specification governance

OBIS is an open interoperability standard, not a private TRADIX internal contract. Its normative specification, schemas, and conformance tests MUST be exportable and independently usable.

BRIDEX may steward reference implementations and test tooling. No steward may make protocol conformance dependent on a proprietary service, private registry, or exclusive certification process. Changes require versioned proposals, compatibility analysis, security review, and published migration guidance.

The standard's governance process and long-term stewardship arrangement remain to be finalized before OBIS 1.0.0.

## 20. Open decisions before 1.0.0

An executable Python reference peer, its draft JSON Schema 2020-12 artifact, local integration tests, and an explicit implementation-status record are maintained in [BRIDEX OBIS Reference Implementation](../projects/BRIDEX/reference/obis-python/README.md). The prototype uses loopback-only HTTP and a shared-secret HMAC development profile; it is not a production security profile or OBIS 1.0 implementation.

The security design baseline is documented separately in [OBIS Threat Model](OBIS_THREAT_MODEL.md). It identifies assets, trust boundaries, adversaries, abuse cases, required mitigations, and the security profiles that must be finalized before OBIS 1.0.0. The threat model is a draft and does not itself select or certify a production cryptographic profile.

The following are intentionally not frozen in version 0.1.0:
- Exact identifier URI/namespace scheme.
- Final JSON Schema dialect and canonical schema repository layout.
- First production security profile and cryptographic suite.
- First transport binding and its conformance suite.
- Formal asynchronous operation lifecycle schema.
- Signature/canonicalization profile for portable signed evidence.
- Compatibility and deprecation support windows.
- Independent governance and change-approval process.

These decisions require threat modeling and interoperability prototypes. They MUST NOT be silently assumed by individual implementations.

## 21. Normative independence statement

**OBIS belongs to no mandatory runtime ecosystem. Every Bridge owner must be able to retain, implement, test, operate, and adapt OBIS independently. BRIDEX may help create compliant Bridges; it must never be required to keep them communicating.**
