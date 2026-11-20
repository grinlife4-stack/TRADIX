# TIIS — TRADIX Internal Integration Standard

**Document ID:** TIIS-SPEC-001  
**Status:** Draft specification / architecture baseline  
**Version:** 0.1.0  
**Effective date:** 2026-11-20  
**Authority:** TRADIX  
**Scope:** Communication among TRADIX internal tools, services, agents, records, workflows, and technical subsystems  
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

## 6. Message and event model

TIIS supports request/response and event-driven interaction. Implementations MUST use typed, versioned messages.

Each request or event MUST carry, as applicable:
- TIIS protocol identifier and version.
- Message type.
- Unique message identifier.
- Correlation/causation identifier.
- Sender and recipient component identities.
- Interface and operation/event identifier.
- Issued-at time and expiry/deadline where relevant.
- Schema version.
- Trace/evidence reference where applicable.
- Typed payload.

Responses MUST identify the originating request and return a typed result or structured error. Events MUST define delivery semantics, ordering assumptions, duplicate handling, and consumer acknowledgment behavior.

A component MUST validate message structure, schema, size, sender, authorization, freshness, and operation scope before processing.

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

## 12. Discovery and catalog integration

TRADIX may provide internal catalogs or discovery metadata to help components locate approved interfaces. Discovery is a convenience, not an authorization mechanism and not a mandatory runtime dependency.

Catalog records MUST NOT contain secret values. They SHOULD include component identity, interface version, capabilities, owner, lifecycle state, and contract location.

A catalog outage MUST NOT silently expand permissions or cause a component to accept an unknown peer. Where practical, components should retain the minimum local configuration needed for safe operation during discovery-service outages.

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

Conformance is assessed per interface and version. Passing TIIS tests does not prove OBIS interoperability, product readiness, or production security.

## 15. Governance

TRADIX owns the internal TIIS specification and is responsible for:
- Versioning and publishing the specification.
- Maintaining schemas and reference test fixtures.
- Reviewing compatibility and security changes.
- Maintaining conformance tests.
- Publishing migration and deprecation guidance.

TIIS may evolve with TRADIX internal needs. Changes MUST NOT silently impose new requirements on external peers or independent products. Any external-facing adoption requires a separately declared interface agreement and MUST NOT be represented as OBIS conformance.

## 16. Open decisions before TIIS 1.0.0

The following remain to be decided through implementation evidence:
- Canonical schema dialect and repository layout.
- Internal component identifier format.
- Approved authentication profiles for local, hosted, and cross-environment deployments.
- Event delivery and persistence profiles.
- Trace and audit record schema.
- Compatibility and deprecation windows.
- Exact conformance harness and CI integration.

These details must be settled before a production TIIS 1.0.0 claim. Implementations must not invent undocumented portfolio-wide defaults.

## 17. Normative scope statement

**TIIS is TRADIX's internal integration standard only. It does not govern external interoperability, does not own product interfaces, and does not replace OBIS.**
