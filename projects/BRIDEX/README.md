# BRIDEX

**Project ID:** BRIDEX-PROJECT-001  
**Project type:** Independent specialist software/tooling project  
**Status:** Architecture established; OBIS 0.1 standalone Python reference prototype implemented; production security and full conformance remain pending  
**Parent portfolio:** TRADIX portfolio  
**Operating rule:** Independent identity, source, configuration, data, lifecycle, and runtime boundary

## 1. Purpose

BRIDEX is an independent specialist project for designing, generating, testing, packaging, documenting, and evolving independent Bridge tools.

A Bridge is itself a tool. It is not merely a connector module, plugin, library, or embedded feature of the software to which it connects. Every generated Bridge must have its own identity, version, source, configuration, permissions, runtime, lifecycle, and explicitly assigned owner/operator.

BRIDEX provides one consistent and reusable engineering method for all Bridge instances. It does not centralize destination-specific business logic or become a mandatory runtime service.

## 2. Core model

- **BRIDEX:** the specialist project and engineering/generation system.
- **Bridge:** an independently identifiable tool produced or maintained using the BRIDEX method.
- **Connected project/tool:** an independent peer that exposes or consumes explicitly approved capabilities.
- **OBIS:** the independent interoperability standard implemented by Bridges for external and Bridge-to-Bridge communication.
- **TIIS:** the separate standard for TRADIX-internal communication. A Bridge may use an optional, scoped TIIS-facing adapter when explicitly authorized to connect to TRADIX.

## 3. Non-negotiable principles

The detailed protocol contracts are maintained separately: [OBIS Specification](../../docs/OBIS_SPECIFICATION.md) governs external interoperability, while [TIIS Specification](../../docs/TIIS_SPECIFICATION.md) governs TRADIX-internal integration only. Both are draft baselines at version 0.1.0, not production-ready protocol releases.

1. BRIDEX has an independent project identity, source, roadmap, configuration, data, operations, and lifecycle.
2. Every Bridge is an independent tool and has an explicitly recorded owner/operator. Ownership is not inferred solely from the destination or the generator.
3. BRIDEX uses one common generation, security, packaging, documentation, and conformance method across projects.
4. Destination-specific connection details, mappings, protocol adapters, permissions, and transformation rules reside in the relevant Bridge instance and the connected project's own approved interface boundary.
5. A destination-specific change must not contaminate the generic BRIDEX core or require changes to unrelated Bridges.
6. A released Bridge must continue operating without BRIDEX or TRADIX being online.
7. BRIDEX is not a mandatory hub, broker, relay, registry, identity provider, or runtime gateway.
8. Every peer connection requires explicit identity, trust, authentication, scoped authorization, capability negotiation, and data-sharing approval.
9. No unrestricted discovery, inbound access, outbound network activity, shell execution, or generic command execution is permitted.
10. Source, configuration, protocol specifications, evidence, and operational state must be exportable and replaceable without lock-in.

## 3A. Bridge ownership and portability

BRIDEX is not the default owner of generated Bridge instances. Ownership is explicitly assigned per instance and may belong to the commissioning/using project or tool, or to another designated entity. Generation, operation, maintenance, and ownership are separate roles and must be recorded separately when they differ.

The designated owner must receive the complete source or independently buildable package, build/deployment instructions, schemas, OBIS specifications, tests, dependency/license inventory, and exportable owner-controlled configuration and records. Subject to third-party licenses, the owner must be able to run, modify, fork, transfer, appoint or replace maintainers/operators, and continue development without BRIDEX or TRADIX.

A Bridge must be adaptable to other ecosystems through documented contracts and replaceable adapters. This is not a promise of automatic compatibility with every target; it is a guarantee that a new integration can be implemented without surrendering ownership or rebuilding the Bridge from zero. See [BRIDEX Ownership, Control, and Portability Policy](../../docs/BRIDEX_OWNERSHIP_AND_PORTABILITY_POLICY.md).

## 3B. Executable OBIS reference prototype

A standalone Python reference peer is now maintained at [OBIS Python Reference](reference/obis-python/README.md), with a versioned [OBIS 0.1 JSON Schema](reference/obis-python/schemas/obis-0.1-message.schema.json), direct two-peer loopback transport, request/response authentication for the local development profile, scoped capability authorization, expiry/replay/payload checks, and automated positive/negative tests.

Run it independently from the TRADIX package:

```bash
cd projects/BRIDEX/reference/obis-python
python -m pip install -e ".[dev]"
python -m pytest -q
```

The root CI also runs these reference tests. The reference now includes `ecoscan.inventory.read@1.0` and an explicit per-credential `allowed_resources` grant. Its provider handler is called only after the OBIS peer validates the authenticated credential's project/source grant. This is a development/conformance prototype only: loopback transport and the shared-secret HMAC profile are not approved for production or sensitive workloads. See [implementation status and release gates](reference/OBIS_REFERENCE_IMPLEMENTATION_STATUS.md).

## 3C. Relationship to existing TRADIX infrastructure

BRIDEX may reuse the Artifact Gateway, Tool Catalog, and Tool Adapter Contract as optional supporting capabilities, but none is a substitute for an independent Bridge or the OBIS protocol. Their exact boundaries, PR dependency order, and separation tests are recorded in [BRIDEX Existing Component Integration Map](../../docs/BRIDEX_EXISTING_COMPONENT_INTEGRATION_MAP.md). These components must not become mandatory runtime dependencies for released Bridges.

## 4. Responsibility boundaries

### BRIDEX

- Maintains the common Bridge engineering and generation method.
- Maintains generic Bridge Core capabilities and reusable templates/SDKs.
- Maintains protocol implementation tooling and conformance tests.
- Defines packaging, release, compatibility, security, and lifecycle requirements for generated Bridge tools.
- Does not own connected projects' domain logic, data, credentials, or authorization decisions.
- Does not automatically own generated Bridge instances.

### Each Bridge instance

- Has an explicitly assigned owner/operator and a documented lifecycle.
- Owns its own source or independently exportable implementation, configuration, credentials, runtime, logs, and operational controls.
- Implements OBIS and any explicitly approved, replaceable protocol adapters.
- Contains its own destination-specific connector, field mappings, transformation logic, and endpoint configuration.
- Can be installed, operated, upgraded, disabled, exported, replaced, and decommissioned independently.

### Connected project/tool

- Defines the capabilities it exposes and consumes.
- Controls its own identity, data, secrets, permissions, interface contract, and disclosure policy.
- Approves and can revoke each Bridge's access.
- Must not depend on BRIDEX for its core operation.

### TRADIX

- Acts as the general product/software factory and may build BRIDEX as a specialist project.
- Governs TIIS for its own internal systems.
- May provide development tooling and optional, authorized integration.
- Is not the mandatory runtime intermediary for BRIDEX or any released Bridge.

## 5. Standard generation lifecycle

1. Record the Bridge's purpose, owner/operator, connected peers, and explicit scope.
2. Define peer identities, trust establishment, supported capabilities, data boundaries, and authorization.
3. Select OBIS and only the required, replaceable protocol adapters.
4. Generate the independent Bridge tool from the common BRIDEX method.
5. Add destination-specific mappings and configuration within that Bridge instance and the connected project's approved interface boundary.
6. Run unit, security, protocol, compatibility, failure-isolation, and conformance tests.
7. Package source, schemas, configuration templates, operational documentation, and evidence for independent deployment.
8. Deploy under the Bridge owner's control; verify operation with BRIDEX and TRADIX unavailable.
9. Maintain, upgrade, revoke, export, replace, or decommission the Bridge independently.

## 6. Required acceptance tests

A Bridge is not accepted as independent until evidence demonstrates:

- It has its own stable identity, owner/operator, version, source, and lifecycle.
- It runs without BRIDEX or TRADIX runtime services.
- It communicates with an independently implemented OBIS peer without TRADIX participation.
- It rejects unauthorized peers and out-of-scope capabilities.
- Peer-specific revocation and data-scope isolation work.
- Unsupported versions/capabilities are rejected safely.
- Timeouts, retries, idempotency, cancellation, and partial failures behave as specified.
- Destination-specific changes do not modify unrelated Bridges or the generic core.
- Its source, configuration, schemas, and required operational records can be exported and used to replace the generator.
- No arbitrary shell, command, filesystem, or network execution is exposed.

## 7. Relationship to existing TRADIX capabilities

Existing Tool Catalog, Tool Adapter Contract, and Artifact Gateway capabilities may be reused only where their actual contracts fit a BRIDEX requirement. They are not, individually or together by assumption, a complete Bridge implementation.

- Tool Catalog may hold non-secret Bridge metadata and conformance status.
- Tool Adapter Contract may inform bounded local invocation interfaces, but does not define OBIS interoperability.
- Artifact Gateway may support bounded artifact exchange, but does not define Bridge identity, trust, authorization, or peer communication.

Any reuse must preserve Bridge independence and must not make a released Bridge dependent on TRADIX runtime services.

## 8. Initial delivery boundary

The first BRIDEX delivery is specification and test architecture, not a production connector. It must establish the Bridge Core boundary, OBIS implementation requirements, generation contract, security model, conformance suite, package format, and independence test harness before generating production Bridges for NEXORA, EXVARLI, ECOSCAN, or other projects.

No production deployment, credential creation, external account setup, secret provisioning, or live connection is authorized by this dossier.

## 9. Governing documents

- [Portfolio-Wide Independence and Bridge Standard](../../docs/PORTFOLIO_INDEPENDENCE_AND_BRIDGE_STANDARD.md)
- [Foundational Architecture Charter](../../docs/FOUNDATIONAL_ARCHITECTURE_CHARTER.md)
- [BRIDEX Architecture](../../docs/BRIDEX_ARCHITECTURE.md)
- [Cross-Ecosystem Execution Order](../../docs/BRIDEX_CROSS_ECOSYSTEM_EXECUTION_ORDER.md)
