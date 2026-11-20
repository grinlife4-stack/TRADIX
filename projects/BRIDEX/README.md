# BRIDEX

**Project ID:** BRIDEX-PROJECT-001  
**Project type:** Independent specialist software/tooling project  
**Status:** BRIDEX Engine 0.1 scaffold, manifest validation, deterministic packaging, and package verification implemented; standalone Python/Go OBIS 0.1 reference peers and a TLS 1.3 mTLS candidate implemented and CI-verified for loopback conformance; production security and runtime acceptance remain open  
**Parent portfolio:** TRADIX portfolio  
**Operating rule:** Independent identity, source, configuration, data, lifecycle, and runtime boundary

## 1. Purpose

BRIDEX is the independent specialist project for designing, generating, testing, packaging, documenting, and evolving independent Bridge tools.

A Bridge is itself a tool, not merely a connector module, plugin, library, or embedded feature of another product. Every Bridge must have its own identity, version, source, configuration, permissions, runtime, lifecycle, and explicitly assigned owner/operator.

BRIDEX provides a repeatable engineering method. It does not centralize destination-specific business logic and does not become a mandatory runtime service.

## 2. Architecture boundaries

- **TRADIX:** builds and develops the portfolio's tools and internal engineering capabilities.
- **BRIDEX:** independently operates the Bridge engineering/generation method.
- **Bridge instance:** an independently owned and operated tool generated and packaged through BRIDEX.
- **TIIS:** optional, scoped communication only between authorized TRADIX-internal components. It is not an external Bridge protocol.
- **OBIS:** the independent external interoperability contract for Bridges and independent peers.

The detailed boundaries are recorded in [BRIDEX Architecture](../../docs/BRIDEX_ARCHITECTURE.md), [Ownership and Portability Policy](../../docs/BRIDEX_OWNERSHIP_AND_PORTABILITY_POLICY.md), [Existing Component Integration Map](../../docs/BRIDEX_EXISTING_COMPONENT_INTEGRATION_MAP.md), [OBIS Specification](../../docs/OBIS_SPECIFICATION.md), and [TIIS Specification](../../docs/TIIS_SPECIFICATION.md).

## 3. Non-negotiable principles

1. BRIDEX has its own identity, source, roadmap, configuration, data, operations, and lifecycle.
2. BRIDEX is not the default owner of generated Bridge instances.
3. Owner, operator, and maintainer are distinct roles and must be explicitly recorded.
4. Each generated Bridge must be installable, operable, modifiable, forkable, transferable, and maintainable without BRIDEX or TRADIX.
5. A Bridge's external OBIS operation must not require TIIS, TRADIX, BRIDEX, a shared catalog, a relay, or a central registry.
6. Destination-specific logic, mappings, permissions, and endpoint configuration belong to the Bridge instance and its connected project's approved boundary.
7. No Bridge starts with trusted peers or enabled capabilities.
8. No secret, credential, or live endpoint is generated or provisioned by BRIDEX.
9. BRIDEX is not a mandatory hub, broker, relay, registry, identity provider, or runtime gateway.
10. Every peer connection requires explicit identity, trust, authentication, scoped authorization, capability contract, and data-sharing approval.

## 4. BRIDEX Engine 0.1

The standalone engineering package is maintained in [projects/BRIDEX/engine](engine/README.md). It provides four offline commands:

- `bridex init`: create a new independent Bridge source skeleton with a unique ID, explicit owner/operator assignment evidence, and draft-only defaults.
- `bridex validate`: validate the canonical manifest and explicit package file set.
- `bridex package`: create a deterministic ZIP with a per-file SHA-256 manifest.
- `bridex verify`: verify package integrity and exact file membership without extracting or executing content.

Generated projects start with no peers, no capabilities, an unconfigured OBIS transport/security profile, and no credentials or network code. The generator does not silently activate anything.

## 5. Relationship with existing TRADIX components

TRADIX's Artifact Gateway, Tool Catalog, and Tool Adapter Contract may be used as optional development or delivery support where their contracts fit. Their local TIIS adapters do not replace OBIS and do not become Bridge runtime dependencies.

The current TRADIX TIIS tooling lane provides:
- Artifact Gateway: read-only, project-bound receipt metadata.
- Tool Catalog: read-only get/list/history; writes remain disabled.
- Tool Adapter: bounded request/result codec only; no execution, worker, scheduler, or sandbox.
- Factory conversation adapter: a separate TIIS integration lane with project-scope authorization kept distinct from the outer component identity.

See the integration map for exact boundaries and remaining gates.

## 6. What is not complete

BRIDEX Engine 0.1 is an engineering-plane generator and package verifier, not a Bridge runtime. It does not embed or operate an OBIS peer inside every generated Bridge.

The standalone OBIS Python and Go reference packages implement the draft 0.1 envelope, a loopback-only HMAC development profile, and a TLS 1.3 mTLS candidate with certificate URI/fingerprint binding and bidirectional cross-language loopback tests. They are reference/conformance implementations, not production-ready Bridge runtimes.

Still open: owner-operated CA/trust-anchor lifecycle, issuance and renewal, durable revocation, trust-bundle freshness, durable replay/idempotency, asynchronous operations, production audit, rate/concurrency limits, full independent conformance, and security review. No production endpoint, credential, deployment, or external peer connection is included or authorized.

## 7. Governing documents

- [BRIDEX Architecture](../../docs/BRIDEX_ARCHITECTURE.md)
- [BRIDEX Ownership and Portability Policy](../../docs/BRIDEX_OWNERSHIP_AND_PORTABILITY_POLICY.md)
- [BRIDEX Existing Component Integration Map](../../docs/BRIDEX_EXISTING_COMPONENT_INTEGRATION_MAP.md)
- [OBIS Specification](../../docs/OBIS_SPECIFICATION.md)
- [OBIS Threat Model](../../docs/OBIS_THREAT_MODEL.md)
- [TIIS Specification](../../docs/TIIS_SPECIFICATION.md)
