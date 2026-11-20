# BRIDEX — Architecture and Engineering Boundaries

**Document ID:** BRIDEX-ARCH-001  
**Status:** Architecture baseline; BRIDEX Engine 0.1 implemented; OBIS production security and Bridge runtime conformance pending  
**Version:** 0.1.0  
**Authority:** Project owner  
**Scope:** BRIDEX project and every Bridge tool generated or maintained under its method

## 1. Architectural definition

BRIDEX is an independent specialist engineering project. Its product is not one central network gateway. Its product is a repeatable method and reusable engineering foundation for generating independent Bridge tools.

A generated Bridge is a standalone tool. It is not a runtime child process that must call home to BRIDEX, and it is not automatically embedded in or owned by the software to which it connects.

## 2. Logical architecture

### A. BRIDEX engineering plane

This plane is used to design and produce Bridge tools. It may contain:

- Bridge Core source and reference implementation.
- Protocol/schema definitions and compatibility tooling.
- Generation templates and project-specific scaffolding.
- Security and policy validation tooling.
- Conformance test harnesses.
- Packaging, release, migration, and documentation tooling.

The engineering plane is not in the runtime path of released Bridges.

**Implemented engineering-plane baseline:** `projects/BRIDEX/engine` provides `bridex init`, `validate`, `package`, and `verify`. It creates draft-only Bridge skeletons with explicit owner/operator assignment evidence, no trusted peers, no enabled capabilities, and no configured OBIS transport. It validates a canonical manifest, packages an explicit file allowlist into a deterministic integrity-manifested ZIP, and verifies packages without extracting or executing content. It has no network access or runtime dependency on TRADIX.

### B. Generated Bridge tool

Each generated instance is an independently deployable product containing:

- Stable Bridge identity and implementation version.
- OBIS protocol implementation.
- Optional, replaceable transport/protocol adapters.
- Peer identity and trust configuration.
- Scoped authentication and authorization enforcement.
- Capability negotiation and typed request/response handling.
- Destination-specific mappings and transformations.
- Bounded queues/retries, idempotency, cancellation, and failure handling.
- Audit/evidence output and health/lifecycle endpoints.
- Exportable configuration and operational documentation.

A Bridge may expose approved capabilities and consume approved capabilities from peers. It must not assume a single direction or a central hub.

### C. Connected peer

Each connected project, tool, service, platform, or other Bridge is a separate trust and data boundary. It defines what it exposes, what it accepts, and what data may cross the boundary.

## 3. Configuration and change isolation

The generic BRIDEX foundation contains only reusable communication behavior and stable contracts.

Each Bridge instance contains its own:
- Peer and endpoint declarations.
- Authentication mechanism configuration and secret references.
- Capability allowlist and authorization scopes.
- Data schemas, field mappings, and transformation rules.
- Transport selection and retry/timeout limits.
- Audit, retention, and operational policy settings.

The connected project independently controls its own API/interface contract, exposed capabilities, data classification, and access approval.

A change to one destination's endpoint, schema, mapping, or permission must be isolated to that Bridge instance and the destination's approved interface. It must not require modifying BRIDEX core or another Bridge.

No secret is embedded in generated templates, shared catalogs, source examples, or project-wide configuration.

## 4. Protocol boundaries

The detailed protocol contracts are maintained as separate specifications: [OBIS Specification](OBIS_SPECIFICATION.md) governs external interoperability, while [TIIS Specification](TIIS_SPECIFICATION.md) governs TRADIX-internal integration. Both are currently draft baselines at version 0.1.0; neither should be treated as production 1.0 conformance until its open decisions, schemas, profiles, and conformance suites are completed and validated.

### OBIS

OBIS is the external interoperability contract carried by each Bridge. It must be independently specified, versioned, testable, and implementable without TRADIX or BRIDEX runtime dependencies.

At minimum, the OBIS envelope and behavior must define:
- Protocol and schema version.
- Sender and recipient identities.
- Bridge identity and implementation version.
- Message identifier and correlation identifier.
- Operation/capability identifier.
- Issued-at and expiry/freshness constraints.
- Payload type, bounded payload, and content classification.
- Authentication context and requested authorization scope.
- Response outcome and normalized error category.
- Evidence/audit reference where applicable.

OBIS must define handshake, capability negotiation, authorization, data boundaries, request/response, reliability, errors, versioning, audit/evidence, and health/lifecycle behavior.

### TIIS

TIIS is only for communication within TRADIX and an explicitly authorized optional TRADIX-facing adapter. It is not translated into or required by OBIS. Loss of TIIS or TRADIX must not break a Bridge's external OBIS communication.

### Other protocols

A Bridge may use other protocols through explicit, replaceable adapters. Such adapters must declare their protocol, version, scope, security properties, and conformance status. A vendor-specific protocol must not silently become part of the OBIS core.

## 5. Security and trust model

The detailed security baseline is maintained in [OBIS Threat Model](OBIS_THREAT_MODEL.md). Production security-profile selection must follow threat-model review and independent negative testing; the existence of this draft does not constitute production security approval.

- No implicit trust based on network location, portfolio membership, catalog registration, or successful handshake.
- Each peer relationship is explicitly configured and independently revocable.
- Authentication identifies the peer; authorization separately controls operations and data scopes.
- Capability negotiation is not permission.
- Default deny for unconfigured peers, operations, fields, and data flows.
- Enforce least privilege, credential rotation, expiry, and revocation.
- Protect against replay, stale messages, oversized payloads, schema confusion, and confused-deputy behavior.
- No generic shell, script, command, arbitrary filesystem access, or unrestricted outbound network facility.
- All consequential operations produce attributable audit evidence without leaking secrets or unnecessary payloads.

## 6. Reliability and fault isolation

- Separate-process/service execution is the default for each Bridge instance.
- In-process execution requires documented justification and equivalent isolation, resource bounds, and failure containment.
- Explicit connect/read/operation deadlines and bounded retries.
- Idempotency keys for operations where retries could duplicate effects.
- Cancellation and partial-failure semantics.
- Circuit breaking/backpressure where appropriate.
- Local state and queues are scoped to the Bridge owner and are exportable.
- A Bridge failure must not crash or corrupt the connected project's core runtime.
- BRIDEX unavailability must not affect released Bridge runtime behavior.
- TRADIX unavailability must not affect OBIS interoperability.

## 7. Ownership, lifecycle, and portability

Ownership, generation, operation, and maintenance are distinct roles. BRIDEX is the generator and engineering-method provider, not the default owner of a generated Bridge. Each instance must explicitly designate its owner; the commissioning/using project or tool may own it, or another entity may be named. If operator or maintainer differs, record that role separately.

The designated owner must have access to the complete source or independently buildable package and, subject to third-party licenses, the rights to run, configure, modify, fork, transfer, independently maintain, appoint/replace operators, and export owner-controlled configuration and operational records. An opaque binary, hosted endpoint, or generator-dependent package alone is insufficient unless a documented exception is explicitly approved.

Portability means the released Bridge can be built, deployed, operated, and maintained without BRIDEX/TRADIX runtime services, repositories, registries, credentials, or license checks. Its release package includes reproducible build/deployment instructions, OBIS specifications, configuration schemas, replaceable adapter contracts, dependency/license inventory, conformance evidence, and migration/export procedures.

The owner can adapt the Bridge to other ecosystems through documented interfaces and replaceable adapters. This does not imply automatic compatibility with every target; it means a new adapter or mapping can be added without surrendering ownership or rebuilding the entire Bridge. The binding detail is in [BRIDEX Ownership, Control, and Portability Policy](BRIDEX_OWNERSHIP_AND_PORTABILITY_POLICY.md).

Every Bridge instance must record:
- Bridge ID and implementation version.
- Owner/operator and maintenance contact/authority.
- Connected peer IDs and authorized scopes.
- Source/package location and integrity evidence.
- Configuration schema and non-secret configuration export.
- Secret references (never secret values in metadata).
- Supported OBIS and adapter versions.
- Conformance and security test evidence.
- Deployment, backup, restore, upgrade, rollback, revocation, replacement, and decommissioning procedures.

Ownership is assigned explicitly for each Bridge instance. The project that commissioned or uses the Bridge may own it, or another explicitly designated entity may own and operate it. BRIDEX's role as generator does not automatically make BRIDEX the owner. The connected destination does not automatically become the owner merely because it is a peer.

## 8. Reuse of existing TRADIX components

Reuse is conditional on contract fit and must not introduce a runtime dependency:

| Existing capability | Potential reuse | Boundary |
|---|---|---|
| Tool Catalog | Non-secret Bridge descriptors, versions, capabilities, lifecycle/conformance metadata | Registration grants no trust, permission, or runtime dependency |
| Tool Adapter Contract | Bounded local invocation model and typed result/evidence concepts | Not an external interoperability protocol and not a Bridge by itself |
| Artifact Gateway | Optional bounded artifact transfer and read-back verification | Not identity, handshake, authorization, or general peer interoperability |

The existing PRs are open/draft and unmerged in the current review baseline. Their status must be rechecked before implementation depends on them. BRIDEX must keep replaceable interfaces around any reused capability.

## 9. Required conformance layers

1. **Core conformance:** envelope/schema validation, identity, version negotiation, typed operations, normalized errors.
2. **Security conformance:** authentication, authorization scopes, deny-by-default, revocation, replay protection, data isolation.
3. **Reliability conformance:** timeouts, bounded retries, idempotency, cancellation, partial failure, backpressure.
4. **Interoperability conformance:** independently implemented Bridge-to-Bridge and Bridge-to-non-TRADIX endpoint communication without TRADIX.
5. **Independence conformance:** runtime tests with BRIDEX and TRADIX unavailable; no hidden registry, relay, credentials, or online license dependency.
6. **Lifecycle conformance:** export, restore, upgrade, rollback, replacement, and decommissioning.
7. **Isolation conformance:** destination-specific changes do not affect the shared core or other Bridge instances.

Passing unit tests alone is not proof of external interoperability or production readiness.

## 10. Delivery sequence

- **Phase 0 — Architecture and ownership baseline:** established in the BRIDEX dossier, architecture, threat model, and ownership/portability policy.
- **Phase 1 — Protocol specifications:** OBIS 0.1 and TIIS 0.1 draft specifications and schemas exist. TIIS is internal-only; OBIS is the external Bridge protocol. Neither is a production 1.0 release.
- **Phase 2 — BRIDEX engineering plane:** implemented as Engine 0.1: scaffold, manifest validation, deterministic package generation, and package verification. New Bridge projects remain draft-only and inert.
- **Phase 3 — OBIS reference and mTLS candidate:** Python and Go standalone peers now implement the draft envelope and TLS 1.3 mTLS candidate with certificate URI/fingerprint binding; bidirectional loopback tests exist. Production credential lifecycle, durable replay/idempotency, revocation, trust-bundle freshness, and security review remain open.
- **Phase 4 — Expanded cross-language conformance:** broaden shared positive/negative vectors to malformed envelopes, expiry, replay, timeouts, revocation, and failure recovery; prove an installed Bridge operates without TRADIX/BRIDEX.
- **Phase 5 — Generated Bridge acceptance:** add destination-specific capability contracts, owner-approved peers, scoped authorization, operational audit, failure isolation, export/restore, and replacement tests.
- **Phase 6 — First pilot:** select one low-risk integration only after all preceding gates pass and the owner explicitly approves the scope.
- **Phase 7 — Portfolio rollout:** generate additional Bridge instances only after the first pilot passes and each project's scope/permissions are approved.

No production Bridge, live credential, external account, secret, deployment, or network connection is authorized by this architecture document alone.

## 11. Explicit non-goals

BRIDEX is not:
- A mandatory message broker, hub, relay, registry, or central identity provider.
- A shared database or centralized repository for all project payloads.
- A mechanism for unrestricted project discovery or automatic data sharing.
- A way to bypass a connected project's authorization or security policy.
- A replacement for the domain APIs or internal logic of connected products.
- A runtime service that every generated Bridge must call.
- A reason to move project-specific logic into a centralized TRADIX or BRIDEX codebase.
