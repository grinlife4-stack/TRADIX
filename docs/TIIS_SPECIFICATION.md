# TIIS — TRADIX Internal Integration Standard

**Document ID:** TIIS-SPEC-001  
**Status:** Versioned 0.1 contract baseline; transport/security profiles and runtime conformance remain incomplete  
**Version:** 0.1.0  
**Effective date:** 2026-11-20  
**Authority:** TRADIX  
**Scope:** Communication among TRADIX internal tools, services, agents, records, workflows, and technical subsystems  
**Canonical envelope schema:** `standards/tiis/0.1/message.schema.json` (JSON Schema Draft 2020-12)  
**Normative language:** The terms MUST, MUST NOT, REQUIRED, SHOULD, SHOULD NOT, and MAY are to be interpreted as normative requirements.

## 1. Purpose

TIIS defines the internal integration contract for components operating within the TRADIX engineering and production boundary. It provides consistent rules for identity, interface declarations, typed requests and responses, authorization, data boundaries, reliability, errors, audit evidence, versioning, and conformance.

TIIS is an internal TRADIX standard. It is not an external interoperability requirement and must not become a dependency for independently owned products, third-party systems, or OBIS peers.

## 2. Scope and exclusions

TIIS applies only when both communicating components are explicitly within the TRADIX internal boundary, or when a separately authorized adapter connects a Bridge to a TRADIX internal component.

TIIS does not govern:
- Bridge-to-external-peer communication.
- Independent Bridge-to-Bridge communication outside TRADIX.
- Product-to-third-party integrations merely because TRADIX built the product.
- Public APIs or external partner interfaces unless separately adopted through a documented contract.
- Product runtime behavior after the product has been separated from TRADIX, except for an explicitly retained TIIS adapter.

An external component MUST NOT be required to implement TIIS to communicate with a product Bridge. OBIS remains the independent standard for Bridge external interoperability.

## 3. Governing principles

1. **Internal scope only:** TIIS MUST NOT be presented as a universal external protocol.
2. **Explicit ownership:** Every internal interface has an owning component and an accountable maintainer.
3. **Typed contracts:** Requests, responses, events, and errors MUST have versioned schemas.
4. **Least privilege:** Internal network location or repository membership MUST NOT grant unrestricted access.
5. **Data separation:** Component ownership and data boundaries remain explicit even inside TRADIX.
6. **Replaceability:** An internal component must be replaceable through a documented interface where practical.
7. **No silent coupling:** Hidden shared state, undocumented imports, and unversioned database coupling are prohibited for cross-component integration.
8. **Observable behavior:** Consequential calls and state transitions must produce attributable evidence.
9. **Fail safely:** Timeouts, partial failures, duplicate delivery, and unavailable dependencies must have declared behavior.
10. **No automatic product ownership:** TRADIX internal integration does not transfer ownership of a product's data, accounts, credentials, or operations.

## 4. Component and interface identity

Each participating component MUST declare:
- Stable component identifier and human-readable name.
- Owning project or internal subsystem.
- Responsible maintainer.
- Interface identifier and version.
- Supported request/response/event schemas.
- Authentication and authorization mechanism.
- Data classification and permitted scope.
- Operational owner and escalation path.
- Dependency and lifecycle status.

A component identity, service identity, agent identity, and human identity MUST remain distinguishable. Identity registration is not authorization.

For TIIS 0.1, project_id and component_id are separate, stable lower-case identifiers matching the canonical schema's slug rule. A runtime instance_id MAY be added when multiple instances of one component must be distinguished. Renaming an identifier is a governed compatibility change; identifiers MUST NOT be recycled for a different component.

The sender and recipient fields in a message are routing/claim fields, not proof of identity. The receiving component MUST bind the claimed sender to an authenticated transport principal or an explicitly trusted local adapter before authorization.

## 5. Interface contract

Every TIIS interface MUST publish a contract containing:
- Interface purpose and owner.
- Supported operations and event types.
- Input and output schemas with versions.
- Required scopes and authorization rules.
- Side-effect classification and idempotency behavior.
- Timeout, retry, and payload limits.
- Error categories and safe recovery guidance.
- Data classification, retention, and audit requirements.
- Compatibility, deprecation, and migration policy.

Operations SHOULD be narrow and domain-oriented. Generic command execution, unrestricted filesystem access, unrestricted database access, or broad administrative capabilities MUST NOT be exposed as ordinary integration operations.

TIIS defines the outer component-to-component envelope; it does not replace interface-owned domain contracts. A domain message schema MUST remain the payload contract for its interface. A domain actor or conversational role carried inside that payload is not the TIIS component identity and MUST NOT be used as proof of the authenticated sender.

## 6. Message and event model

TIIS 0.1 defines a transport-neutral JSON envelope. HTTP, local IPC, queues, or another transport MAY carry the envelope, but transport selection MUST be declared by the interface owner and MUST NOT change the envelope's identity or authorization rules.

The canonical envelope schema is standards/tiis/0.1/message.schema.json. It defines three message types:

- **request:** requires a unique message_id, interaction correlation_id, sender, recipient, interface identity/version, operation, issued_at, expires_at, and object payload. A state-changing operation whose retry could duplicate an effect MUST require an idempotency_key in its interface contract.
- **response:** requires correlation_id, in_reply_to, sender/recipient, interface identity/version, issued_at, outcome, and object payload. Failed or rejected responses MUST include a normalized error object.
- **event:** requires a unique message_id, sender/recipient, interface identity/version, issued_at, event type, and object payload. message_id is the event identity for deduplication.

The envelope MUST use protocol: "TIIS" and protocol_version: "0.1". message_id, correlation_id, and in_reply_to use UUID values. Interface and component identifiers use the canonical lower-case identifier form. Timestamps MUST be RFC 3339 date-time values with an explicit UTC offset. The receiver MUST reject unknown top-level fields in version 0.1; payload schemas are declared and versioned by each interface.

The envelope MUST NOT carry passwords, API keys, bearer tokens, private keys, raw credentials, or secret values. Authentication material belongs to the transport or an owner-controlled credential mechanism and MUST never be copied into message payloads.

Responses MUST identify the originating request and return a typed result or normalized error. A receiver MUST validate the envelope, payload schema, size, authenticated sender binding, recipient, freshness, authorization, and operation scope before processing. Schema validation alone does not authenticate a sender or authorize an operation.

## 7. Security and authorization

TIIS components MUST authenticate each other using an approved internal mechanism appropriate to the deployment. Authentication and authorization MUST remain separate.

- Default deny for unregistered or unauthorized callers.
- Explicit operation and data scopes.
- Least-privilege service identities.
- Credential expiry, rotation, and revocation.
- Protection against replay and confused-deputy behavior.
- No secrets in source code, event payloads, logs, or catalog metadata.
- Separate development, test, staging, and production identities and policies.
- Administrative actions require explicit privileged scopes and attributable evidence.

A successful internal handshake or service discovery result MUST NOT grant authorization.

The authenticated identity MUST come from the configured transport/security layer or a specifically trusted local adapter, never from an unverified sender field. The receiver MUST compare that authenticated identity with the declared sender and its local peer policy. If no approved authentication profile is configured for an interface, the interface MUST remain disabled; there is no anonymous or permissive fallback in TIIS 0.1.

## 8. Data ownership and boundaries

Each component remains responsible for the data it owns. TIIS does not authorize one component to read or modify another component's data by default.

Cross-component data access MUST be:
- Explicitly approved by the data-owning component.
- Limited to declared fields and purposes.
- Versioned and schema-validated.
- Logged where access is sensitive or consequential.
- Subject to retention, export, correction, and deletion rules.
- Revocable without requiring unrelated components to be rewritten.

Direct database sharing is not the default integration method. Where shared persistence is approved, ownership, schema boundaries, migration authority, access roles, and failure behavior MUST be documented. Consumers MUST NOT silently depend on another component's private tables or internal schema.

## 9. Reliability and execution semantics

Every operation MUST declare applicable:
- Connect/read/processing deadlines.
- Retry policy and retryable outcomes.
- Idempotency key requirements.
- Cancellation semantics.
- Partial-failure behavior.
- Rate and payload limits.
- Backpressure and overload response.
- Outcome reconciliation procedure for timeouts.

A timeout does not prove that a side effect did not occur. State-changing operations SHOULD support idempotency or a status/evidence query. Consumers MUST NOT blindly repeat an operation whose outcome is unknown.

For asynchronous operations, the contract MUST define accepted, running, completed, failed, cancelled, and expired states as applicable.

TIIS 0.1 does not promise exactly-once event delivery. Event consumers MUST be idempotent and deduplicate by message_id. Unless an interface explicitly defines a sequence number and ordering scope, consumers MUST assume events may be duplicated, delayed, or reordered. Where loss is unacceptable, the producer MUST use a durable producer-owned outbox and the consumer MUST use a durable consumer-owned inbox/checkpoint; shared database tables are not implied. Acknowledgment means the receiver has durably accepted the event, not that every downstream business effect has completed.

## 10. Errors and observability

Errors MUST use stable machine-readable categories, safe messages, and correlation references. Raw stack traces, secrets, private file paths, and unnecessary sensitive data MUST NOT cross component boundaries.

Internal observability SHOULD include:
- Request and event correlation.
- Authentication and authorization decisions.
- Operation outcome and duration.
- Retry, timeout, and duplicate-delivery events.
- Configuration and schema changes.
- Lifecycle and health transitions.

Audit evidence must be attributable and protected from unauthorized alteration. Each component's owner controls its logs and records subject to portfolio-wide security and retention requirements.

## 11. Versioning and compatibility

Interfaces and schemas MUST be versioned independently of the component release where practical.

- Backward-compatible additions SHOULD use a MINOR version increment.
- Breaking changes MUST use a MAJOR version increment.
- Unknown required fields/features MUST cause explicit rejection.
- Unknown optional fields may be ignored only where the schema permits.
- Deprecation MUST include a replacement, migration guidance, and support window.
- Consumers MUST NOT silently assume that producer and consumer versions are compatible.

A component owner is responsible for publishing compatibility information and migration guidance for its interfaces.

TIIS 0.1 uses Semantic Versioning for interface contracts. The protocol envelope version and each interface version are independent. A producer MUST publish the versions it supports; a consumer MUST explicitly select a compatible version and MUST fail closed on an unsupported major version. Each interface owner MUST declare a deprecation date and migration/support window before announcing a breaking replacement; TIIS 0.1 does not impose one portfolio-wide duration until the TRADIX runtime inventory establishes a support policy.

## 12. Discovery and catalog integration

TRADIX may provide internal catalogs or discovery metadata to help components locate approved interfaces. Discovery is a convenience, not an authorization mechanism and not a mandatory runtime dependency.

Catalog records MUST NOT contain secret values. They SHOULD include component identity, interface version, capabilities, owner, lifecycle state, and contract location.

A catalog outage MUST NOT silently expand permissions or cause a component to accept an unknown peer. Where practical, components should retain the minimum local configuration needed for safe operation during discovery-service outages.

The first TRADIX Tool Catalog interface is `tool.catalog@1.0.0`, implemented by `src/tradix/tools/tiis_adapter.py`. It exposes only `tool.get` and `tool.list` read operations and returns correlated TIIS response envelopes. It is an in-process adapter contract: the caller must supply a principal from a trusted authentication boundary. It does not create a network listener, authenticate credentials, mutate lifecycle state, install tools, or execute tools. Artifact Gateway and other network-facing components remain outside TIIS until an approved transport identity profile and scoped authorization mapping are implemented and tested.

## 13. Relationship with OBIS and Bridge adapters

TIIS and OBIS are separate standards with separate scopes, versioning, schemas, conformance tests, and failure boundaries.

- TRADIX internal component ↔ TRADIX internal component: TIIS.
- Bridge ↔ authorized TRADIX internal component: optional, scoped TIIS-facing adapter.
- Bridge ↔ external tool/service/platform or independent Bridge: OBIS or a separately declared replaceable adapter.
- Independent Bridge ↔ independent Bridge outside TRADIX: direct OBIS communication where supported.

A TIIS adapter MUST NOT be required for a Bridge's OBIS operation. Translating an external OBIS request into TIIS is an implementation detail permitted only inside an explicitly authorized adapter; it must not make TRADIX a mandatory relay or policy authority for the external peer.

Loss of TRADIX discovery or internal services may disable the corresponding internal integration, but MUST NOT disable the Bridge's independent OBIS operation.

## 14. Conformance and validation

A component may claim TIIS conformance only after tests demonstrate:
- Contract and schema validation.
- Component identity and authorization enforcement.
- Default-deny and revocation behavior.
- Data-scope enforcement.
- Version negotiation and safe incompatibility handling.
- Timeout, retry, idempotency, and partial-failure semantics.
- Error normalization and audit evidence.
- Independent failure boundaries and documented recovery.

Conformance is assessed per interface and version. TRADIX provides an optional SDK under src/tradix/tiis, installable with the tiis extra. TIISValidator checks the canonical envelope schema, message-size bound, freshness/expiry, authenticated-sender binding, recipient binding, and a caller-supplied authorization policy. The SDK does not authenticate peers, implement a transport, persist events, or execute business operations. Canonical schema and SDK package copies are checked for byte equality; schema and runtime tests are included in the root test suite.

A component or interface may claim TIIS conformance only after its own authentication profile, authorization policy, data-scope enforcement, replay/freshness, reliability, audit, and failure-isolation tests pass. Passing SDK tests does not prove component runtime conformance, OBIS interoperability, product readiness, or production security.

## 15. Governance

TRADIX owns the internal TIIS specification and is responsible for:
- Versioning and publishing the specification.
- Maintaining schemas and reference test fixtures.
- Reviewing compatibility and security changes.
- Maintaining conformance tests.
- Publishing migration and deprecation guidance.

TIIS may evolve with TRADIX internal needs. Changes MUST NOT silently impose new requirements on external peers or independent products. Any external-facing adoption requires a separately declared interface agreement and MUST NOT be represented as OBIS conformance.

## 16. TIIS 0.1 baseline decisions

The following decisions are normative for the 0.1 envelope and schema:

1. **Schema:** JSON Schema Draft 2020-12. The canonical schema lives under standards/tiis/0.1/; tests live in the root tests/ suite.
2. **Identifiers:** project and component identifiers are separate lower-case slugs; runtime instance identity is optional. Message and correlation identifiers are UUIDs.
3. **Envelope:** one transport-neutral JSON envelope with request, response, and event variants. Interface payload schemas remain interface-owned.
4. **Authentication boundary:** authentication is external to the envelope. The authenticated transport principal must be bound to the claimed sender. No default authentication profile is approved yet; an interface without an explicitly configured profile remains disabled.
5. **Events:** at-least-once delivery is the only assumed delivery model. Consumers deduplicate by message_id; ordering is not assumed unless an interface declares it. Durable outbox/inbox storage is required when the interface's loss policy requires it.
6. **Tracing:** optional trace context uses 32-character lowercase hexadecimal trace IDs and 16-character lowercase hexadecimal span IDs. Trace identifiers are observability metadata, not identity or authorization.
7. **Compatibility:** Semantic Versioning applies independently to interfaces. Each interface owner publishes its own deprecation and migration window.
8. **Conformance:** schema validation is automated in repository CI. Runtime conformance is assessed separately for each interface and deployment profile.

## 17. Open decisions before TIIS 1.0.0

The following require inventory and implementation evidence before a production 1.0.0 claim:
- Approved authentication profiles for local process, same-host service, hosted service, and cross-environment communication.
- Credential issuance, rotation, revocation, principal-to-component binding, and emergency deny behavior for each approved profile.
- Durable event transport and storage implementations, including recovery and retention guarantees.
- Canonical audit event schema, tamper-evidence requirements, retention, export, and access controls.
- Portfolio-wide minimum deprecation/support window, after inventorying all TRADIX internal consumers.
- End-to-end conformance harness covering real internal components, not only schema fixtures.
- Security review and failure-injection evidence for each production transport.

Until these gates pass, TIIS 0.1 is a contract/schema baseline, not a production-ready internal communication runtime. Implementations MUST NOT invent undocumented portfolio-wide defaults or claim production conformance.

## 18. Normative scope statement

**TIIS is TRADIX's internal integration standard only. It does not govern external interoperability, does not own product interfaces, and does not replace OBIS.**
