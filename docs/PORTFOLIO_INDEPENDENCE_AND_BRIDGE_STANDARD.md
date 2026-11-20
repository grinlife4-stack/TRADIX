# Portfolio-Wide Independence and Bridge Standard

**Document ID:** TRADIX-ARCH-BRIDGE-001  
**Status:** GOVERNING / MANDATORY  
**Scope:** Every current and future product, project, application, service, tool, agent, factory, and technical subsystem in the portfolio  
**Authority:** Project owner  
**Effective date:** 2026-11-20  
**Precedence:** Subordinate only to an explicitly approved, versioned amendment by the project owner

## 1. Governing rule

Every portfolio product and tool must retain an independent identity and operating boundary. TRADIX-internal components communicate under the TRADIX Internal Integration Standard (TIIS). When a product or tool communicates across its boundary, its dedicated Bridge uses TIIS only for its explicitly authorized TRADIX-facing interface and the independent Open Bridge Interoperability Standard (OBIS) for connections to non-TRADIX tools, services, and other Bridges.

**A Bridge is an independent tool owned and controlled by the relevant portfolio project, never by BRIDEX. BRIDEX is only the specialist engineering project that designs, generates, tests, packages, and evolves Bridge tools. For a Bridge that exposes a project's resources or capabilities, that source/resource-owning project owns the Bridge instance. Each Bridge has its own identity, source, configuration, permissions, runtime, lifecycle, and operational boundary. A connected project is a peer and integration party, not automatically the owner of the other project's Bridge.**

This is a default architectural requirement. It must be applied automatically during the creation, design, implementation, review, testing, release, and maintenance of every new or existing product and tool. Reconfirmation is not required for routine compliance.

**This standard does not introduce independence as a new strategic objective. Independence is the founding purpose of the TRADIX architecture from its inception.** This document translates that existing foundational purpose into explicit, testable engineering requirements for ownership boundaries, runtime autonomy, interoperability, data portability, security, and lifecycle control. It is an implementation and enforcement standard, not a change of direction or a new dependency on TRADIX.

## 2. Ownership and responsibility boundaries

### TRADIX owns

- TIIS: the internal integration standard used by TRADIX's own tools, services, agents, records, and technical subsystems.
- The TIIS schemas, versioning policy, internal compatibility rules, and conformance tests.
- The TRADIX-facing Bridge adapter/profile that allows an independently owned Bridge to communicate with authorized TRADIX components.
- Reference implementations, generation templates, SDKs, and documentation for TIIS and its Bridge-facing adapter.

TRADIX does not own or control OBIS as a runtime dependency. OBIS is the independent interoperability standard carried and implemented by each Bridge so that the Bridge remains usable outside TRADIX. TRADIX may publish compatible documentation or optional reference tooling, but OBIS must remain implementable and operable without TRADIX.

### BRIDEX owns and maintains

- The specialist Bridge engineering project, its generation method, reusable Bridge Core, protocol implementation tooling, templates, SDKs, and conformance tooling.
- The common generation and validation process used to produce Bridge tools consistently across projects.
- The generic capabilities that belong in the reusable Bridge foundation, without absorbing destination-specific business rules.

### Each Bridge instance has

- An explicitly designated owner with documented rights to obtain the complete source/package, build and run it independently, modify and fork it, transfer it, appoint or replace maintainers/operators, and export owner-controlled configuration and operational records, subject to third-party licenses.
- Ownership is distinct from generation, operation, and maintenance. The project whose resources/capabilities are exposed through the Bridge owns that Bridge instance. BRIDEX must never own a project Bridge merely because it generated, packaged, tested, or maintains it. The project may appoint an operator or maintainer without transferring ownership.
- A complete portability/exit package and documented adaptation path so the owner can move the Bridge to another repository, build environment, operator, or ecosystem without BRIDEX/TRADIX runtime dependencies.
- A machine-readable and human-readable ownership record. Missing or ambiguous ownership blocks release.

- Its own identity as an independent tool, versioned implementation, repository or independently exportable source package, runtime, configuration, credentials, permissions, logs, and lifecycle.
- An explicitly recorded owner/operator responsible for its operation, security, maintenance, release, and decommissioning. Ownership is assigned per Bridge instance; it is not inferred solely from which system it connects to or which factory generated it.
- Its own destination-specific connector, mappings, protocol adapters, and connection settings. These remain inside that Bridge instance and the connected project's own approved interface/configuration boundary.

### Each connected product or tool owns

- Its internal business/domain logic and the capabilities/data it chooses to expose.
- Its own interface contract, authorization decisions, data classification, and approval of the Bridge's access.
- Its own configuration and records that are specific to its internal operation.
- Its own configuration, credentials, permissions, secrets, runtime, logs, and operational controls.
- Its data-retention, export, recovery, replacement, and decommissioning procedures.
- Decisions about which capabilities and data it exposes through the Bridge.

TRADIX must not become the repository of product-specific Bridge logic, operational data, credentials, or internal domain models merely because it defines the standard.

### Project ownership rule for every Bridge

1. Every project-specific Bridge instance is owned by the portfolio project whose resources, data, or capabilities it is authorized to expose. The project retains final authority over its Bridge identity, source/package, configuration, credentials, permissions, release, operation, maintenance appointments, suspension, replacement, and retirement.
2. BRIDEX is a generator and engineering-method provider only. It may not be named as owner, acquire ownership by generating or maintaining a Bridge, or retain exclusive control over source, signing, deployment, credentials, or runtime.
3. A consuming project remains owner of its own receiving adapter, local validation, and data-acceptance boundary. It does not thereby acquire ownership of another project's source-side Bridge.
4. Cross-project integrations use separately owned Bridge instances at each project boundary by default. A shared multi-project Bridge is prohibited unless the affected project owners explicitly approve a written joint-ownership and governance agreement, with per-project identity, credentials, scopes, data isolation, exit, and replacement rights. BRIDEX is not a default joint owner or operator.
5. Missing project ownership, source custody, or an explicit operator assignment blocks release. No ownership may be inferred from repository location, generator, hosting account, or destination.

## 3. Independence requirements

Each Bridge must:

1. Be an independently identifiable tool with an explicitly assigned owner/operator and a documented ownership record.
2. Be deployable and operable independently of TRADIX.
3. Support independent operation of its product when TRADIX is unavailable, unless a separately approved product requirement explicitly defines a bounded online dependency.
4. Avoid making the product's core runtime depend on the Bridge being healthy.
5. Be replaceable, upgradeable, disableable, and recoverable without surrendering product data or identity.
6. Support explicit timeouts, bounded retries, idempotency where applicable, and safe handling of partial failures.
7. Preserve local operation and queue/reconcile permitted work when disconnected, where the product's domain permits it.

A Bridge may run as a separate process or service. This is the preferred default because it isolates resource use, faults, deployment, and security boundaries from the product's core runtime. An in-process implementation is allowed only when justified by technical constraints and when equivalent isolation, resource limits, and failure containment are demonstrated.


## 3A. Multi-party and vendor-neutral interoperability

A Bridge is an independent, general-purpose, standards-based tool that establishes an authorized integration boundary between its peers. It is **not a subcomponent owned automatically by the destination and not a TRADIX-only connector** and must not assume that TRADIX is the hub, broker, gateway, identity provider, or permanent intermediary for all communication.

Subject to the owning product's authorization and security policies, a Bridge must be designed to communicate with:

- TRADIX, when the product chooses to use TRADIX capabilities.
- Other products and tools within the portfolio.
- Independent third-party applications, platforms, and services.
- Other independently owned Bridges, using OBIS or an explicitly supported, replaceable protocol adapter.

The Bridge must support both sides of an integration where relevant: exposing the owner's approved capabilities to authorized peers and consuming approved capabilities exposed by other systems. It must not require every message or transaction to pass through TRADIX.

Interoperability requirements:

1. Use vendor-neutral, documented protocol contracts and open, implementable schemas; avoid TRADIX-specific assumptions in the core protocol.
2. Identify each communicating party independently. A TRADIX identity or registration must not be required to establish a trusted relationship with another authorized system.
3. Require explicit trust establishment, authorization, capability negotiation, and data-sharing approval for each peer or integration.
4. Support direct peer-to-peer communication where appropriate, as well as explicitly configured intermediaries when network, security, or operational constraints require them.
5. Keep protocol translation in replaceable adapters or extensions; do not contaminate the stable core with one vendor's proprietary behavior.
6. Allow integrations to be added, revoked, or replaced without changing the product's internal domain logic or making it dependent on TRADIX.
7. Never interpret interoperability as permission for unrestricted discovery, inbound access, data sharing, or outbound network activity. Connections must be explicitly configured, scoped, authenticated, authorized, and auditable.

TRADIX may publish discovery metadata or operate optional coordination services for TIIS-connected peers, but these must remain replaceable conveniences. OBIS must not require a central TRADIX registry or relay to function.

## 3B. Interoperability conformance

The conformance suite must test at least:

- Bridge-to-Bridge communication between two independently implemented OBIS peers without TRADIX participation.
- Communication with a non-TRADIX endpoint using OBIS or a declared, replaceable protocol adapter.
- Continued OBIS operation when TRADIX discovery, registry, identity, or relay services are unavailable.
- Separate TIIS conformance for the optional TRADIX-facing adapter, without treating TIIS conformance as proof of OBIS interoperability.
- Peer-specific authorization, revocation, and isolation of data scopes.
- Compatibility negotiation and safe rejection of unsupported protocol versions or capabilities.

A Bridge must not be declared externally interoperable solely because it can connect to TRADIX or pass TIIS tests. OBIS interoperability must be tested independently.

## 4. Data and security boundaries

- Expose only explicitly authorized capabilities and the minimum data required for each operation.
- Apply least-privilege authorization, scoped credentials, revocation, and rotation.
- Keep product secrets and credentials under the product's control; do not place them in TRADIX catalog metadata or shared documentation.
- Do not treat a successful handshake as authorization to access every capability or data set.
- Define data classification, permitted fields, retention, audit events, and export boundaries for each exposed operation.
- Treat Bridge input as untrusted. Validate schemas, sizes, identity, freshness, replay protection, and authorization.
- Never allow a generic Bridge operation to become unrestricted shell, script, command, filesystem, or network execution.

## 5. OBIS: independent interoperability contract

The detailed normative draft is maintained in [OBIS Specification](OBIS_SPECIFICATION.md) (version 0.1.0). The TRADIX-only internal contract is separately maintained in [TIIS Specification](TIIS_SPECIFICATION.md) (version 0.1.0). These are independent specifications with separate scopes, governance, versioning, and conformance suites; both remain draft baselines pending schemas, concrete profiles, prototypes, and validation.

OBIS is the protocol contract implemented by each Bridge for communication with non-TRADIX tools, services, platforms, and other independently operated Bridges. Its specification, schemas, compatibility rules, and required runtime behavior must be available with the Bridge and must not require TRADIX repositories, services, credentials, registries, identity systems, or infrastructure to operate.

OBIS must remain vendor-neutral, versioned, transport-adaptable, and independently implementable. Each Bridge must be able to retain and use its OBIS implementation after separation from TRADIX. External requests must never be forced through TIIS, translated into TIIS as a prerequisite, or routed through TRADIX merely to reach an external peer.

The OBIS core must remain small and stable. At minimum it defines:

1. **Identity:** stable product, tool, and Bridge identifiers.
2. **Handshake:** protocol version, supported capabilities, and compatibility declaration.
3. **Request/response:** typed envelopes, correlation identifiers, bounded payloads, and explicit outcomes.
4. **Authorization:** caller identity, scoped permissions, expiry, and revocation behavior.
5. **Data boundary:** declared inputs, outputs, classifications, and permitted disclosures.
6. **Reliability:** timeout, retry, idempotency, cancellation, and partial-failure semantics.
7. **Errors:** stable error categories and safe recovery guidance.
8. **Versioning:** backward-compatibility rules, deprecation windows, and explicit breaking-change policy.
9. **Audit/evidence:** attributable records for security-sensitive and consequential operations.
10. **Health and lifecycle:** readiness, availability, disablement, and graceful shutdown semantics.

Domain-specific behavior belongs in optional, versioned extensions, not in the OBIS core.

## 5A. TIIS: TRADIX-internal integration contract

TIIS is a separate standard for communication among TRADIX-owned internal tools, services, agents, records, workflows, and technical subsystems. TRADIX defines, versions, documents, and tests TIIS. Its schemas and internal compatibility rules are authoritative only within the TRADIX internal boundary and for explicitly authorized TRADIX-facing Bridge adapters.

TIIS is not the external interoperability protocol. A third-party tool or independent Bridge must not be required to implement TIIS merely to communicate with a product's Bridge. A Bridge may include a TIIS adapter when it is authorized to connect to TRADIX, but that adapter is optional to the Bridge's independent operation and must be removable or disableable without breaking OBIS connections.

## 5B. Separation and protocol-selection rules

1. TRADIX internal component to TRADIX internal component: TIIS.
2. Product Bridge to an authorized TRADIX internal component: the Bridge's TIIS-facing adapter/profile, subject to the product's explicit authorization.
3. Product Bridge to a non-TRADIX tool, service, platform, or independent Bridge: OBIS (or a separately declared, replaceable protocol adapter); never a mandatory TIIS path.
4. Bridge-to-Bridge communication outside TRADIX: OBIS directly where supported, without a TRADIX hub, relay, registry, or identity provider.
5. When TRADIX is unavailable or removed, OBIS operation must continue; only the optional TRADIX-facing integration may become unavailable.

TIIS and OBIS must have separate names, specifications, versioning, conformance suites, and failure boundaries. They may share neutral implementation libraries only where this creates no runtime or governance dependency.

## 6. TRADIX catalog boundary

TRADIX may keep only the metadata needed to discover and validate a Bridge, such as:

- Product/tool/Bridge identifiers.
- Protocol and implementation versions.
- Declared capabilities and extension identifiers.
- Compatibility and conformance status.
- A non-secret endpoint or discovery reference, if explicitly permitted.
- Lifecycle status and the date/version of the last conformance result.

The catalog must not store product payloads, detailed operational records, customer data, private keys, access tokens, or product-specific secrets. Catalog registration does not grant access or authority.

## 7. Required lifecycle gate for every project and tool

The following checks are mandatory and must be recorded in the project's dossier or technical decision record:

- [ ] Independent product/tool identity and ownership boundary defined.
- [ ] Bridge recorded as an independent tool with explicit owner/operator, lifecycle, and exportable implementation.
- [ ] Bridge protocol version and supported capabilities declared.
- [ ] Data disclosure and authorization boundaries documented.
- [ ] Independent runtime and failure-isolation design documented.
- [ ] Behavior during TRADIX outage or disconnection tested.
- [ ] Compatibility, conformance, and security tests passed.
- [ ] Export, replacement, revocation, and decommissioning paths documented.
- [ ] Any exception explicitly approved, scoped, time-bounded where appropriate, and recorded.

A project may be developed before its Bridge is needed, but it must not claim conformance or production readiness for TRADIX integration until the applicable checks pass. A missing Bridge must be recorded as a deliberate not-yet-integrated state, not silently treated as compliance.

## 8. Existing systems and conflict handling

This standard applies to existing as well as future portfolio projects and tools. Existing implementations must be assessed against it when they are next materially changed, integrated, or prepared for production. Gaps must be recorded with an owner and a correction plan.

Do not introduce duplicate Bridge frameworks where existing components can be adapted safely. In particular, existing Tool Catalog, Adapter Contract, and Artifact Gateway capabilities must be reviewed for reuse against this standard. They are not automatically equivalent to a complete, independently operated Bridge.

If an existing project-specific document or implementation conflicts with this standard, record the conflict and resolve it through controlled change. Do not silently override the standard.

## 9. Exceptions and change control

No routine project or tool may opt out by convenience. An exception requires explicit project-owner approval and must state its scope, reason, risks, compensating controls, affected systems, and review or expiry condition.

Amendments to this standard require explicit project-owner approval, a versioned change record, rationale, and effective date.

## 10. Foundational statement

**Every Bridge is an independent tool. BRIDEX provides a consistent, reusable method to design, generate, test, and evolve Bridge tools. Each Bridge instance has an explicitly assigned owner/operator; connected projects control their own interfaces, data, and permissions. TRADIX owns TIIS for its internal systems. Each Bridge carries OBIS for independent external interoperability. No Bridge requires TRADIX or BRIDEX to remain operational after generation and release.**
