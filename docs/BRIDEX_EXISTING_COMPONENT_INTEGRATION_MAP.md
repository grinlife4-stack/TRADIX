# BRIDEX — Existing Component Integration Map

**Status:** Architecture boundary record  
**Scope:** Relationship between BRIDEX/OBIS/TIIS and the existing TRADIX artifact, catalog, and adapter work  
**Purpose:** Reuse existing capabilities without mistaking partial infrastructure for a complete Bridge.

## 1. Core boundary

BRIDEX creates and validates independent Bridge tools. OBIS defines their external peer-to-peer interoperability contract. TIIS is only the optional internal integration contract for authorized TRADIX-internal communication.

The existing TRADIX components may support Bridge development, packaging, discovery metadata, or controlled invocation. They do not replace OBIS, do not become mandatory Bridge runtime services, and must not create a central dependency.

## 2. Existing work and its actual capability

| Work item | What it provides | What it does not provide | Relationship to BRIDEX |
|---|---|---|---|
| [PR #45 — Artifact Intake/Gateway](https://github.com/grinlife4-stack/TRADIX/pull/45) | Bounded artifact intake, inspection, content-addressed storage, and configured destination transfer/read-back adapters | General peer interoperability, capability negotiation, Bridge identity, authorization between arbitrary peers, or execution of uploaded artifacts | Optional artifact transport for Bridge packages and evidence. It is not an OBIS transport or Bridge runtime. |
| [PR #46 — Tool Catalog](https://github.com/grinlife4-stack/TRADIX/pull/46) | Persistent metadata, descriptors, evidence references, and lifecycle assertions | Authentication, authorization, trust establishment, live health proof, cryptographic audit, or permission to execute | Optional metadata catalogue. A catalog state must never be interpreted as peer trust or an execution grant. |
| [PR #47 — Tool Adapter Contract](https://github.com/grinlife4-stack/TRADIX/pull/47) | Typed bounded invocation/result contracts, allowlisted job types, resource-policy fields, and fake-adapter tests | Real provider adapters, scheduler, runner, sandbox isolation, credential injection, cancellation backend, or proof of actual resource enforcement | Possible invocation boundary for a Bridge-owned adapter after independent policy checks. It is not an OBIS implementation or secure execution engine. |
| OBIS | External peer identity context, protocol envelope, capability invocation semantics, errors, and conformance requirements | A central registry, mandatory relay, universal discovery, or a generic arbitrary-code execution service | The independent external interoperability contract implemented by Bridges. |
| TIIS | TRADIX-internal component integration contract | External interoperability or authority over independent Bridge peers | Optional, explicitly scoped internal adapter only. |

## 3. Dependency order of existing PRs

The current PR chain is intentional:

1. PR #45 targets `main`.
2. PR #46 is based on PR #45's branch and must follow it.
3. PR #47 is based on PR #46's branch and must follow it.

Do not retarget or merge PR #46 or #47 directly to `main` ahead of their declared base dependencies. This record does not authorize merging any PR.

## 4. Safe integration pattern

A Bridge package lifecycle may use existing components as optional helpers:

1. BRIDEX produces an independently buildable Bridge package, its OBIS version/profile declaration, schemas, tests, dependency inventory, and owner/operator record.
2. Artifact Gateway may receive or transfer the package and evidence, if its destination backend is explicitly configured and the transfer is verified.
3. Tool Catalog may store a metadata descriptor and references to evidence. Catalog approval is not a trust grant.
4. The Bridge owner independently installs and configures the Bridge, its peer identities, trust anchors, credentials, scopes, and lifecycle controls.
5. The Bridge communicates directly with the remote peer using OBIS. No TRADIX catalog, artifact gateway, BRIDEX runtime, or shared relay is required at runtime.
6. If an explicitly authorized TRADIX-internal operation is needed, a separate TIIS adapter may be enabled. Removing that adapter must not disable OBIS.

## 5. Non-negotiable separation tests

- Stop or make TRADIX unavailable: an installed Bridge must still communicate with its configured external peer.
- Stop or remove BRIDEX tooling: an already released Bridge must still operate and be maintainable from its exported package.
- Remove Tool Catalog: the Bridge's peer trust and authorization decisions must remain intact.
- Remove Artifact Gateway: the Bridge must still operate from owner-held source/package and configuration.
- Remove the optional TIIS adapter: external OBIS behavior must remain intact.
- Replace the invocation adapter or runner: the Bridge must retain owner-controlled configuration, permissions, audit, and portability.
- A catalog status, artifact receipt, adapter result, or network address must never substitute for authentication or authorization.

## 6. Current evidence gaps

- PR #45's PR record states that GitHub/S3 destination credentials are not configured in its staging service; live remote transfer remains unverified.
- PR #46 explicitly limits its catalog to metadata and lifecycle assertions.
- PR #47 has fake-adapter contract tests only; no real runner, sandbox, scheduler, or provider integration is implemented.
- The OBIS Python reference is a loopback-only development prototype. Its candidate production TLS/mTLS profile and cross-language interoperability remain unimplemented.

These boundaries must be preserved when the PR chain is integrated. No existing component should be relabeled as a completed Bridge or a production execution/security layer.
