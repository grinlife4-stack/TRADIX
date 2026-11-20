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
- The older OBIS PR #76 candidate failed Go compilation and is not the accepted implementation line. The ordered OBIS candidate is Draft PR #78, stacked on unified BRIDEX Engine PR #77 and TIIS/TRADIX PR #70. Its latest recorded OBIS CI run (44744149965) passed 57 Python tests, Go tests, wheel build/install, schema parity, and independence checks on head `0cf2a45bc1b1e4593bdbfebcd2aa2431d9bebbfd`. Bidirectional Python/Go TLS 1.3 mTLS loopback tests passed; production approval remains open.

These boundaries must be preserved when the PR chain is integrated. No existing component should be relabeled as a completed Bridge or a production execution/security layer.


## 7. TIIS integration status inside TRADIX

TIIS 0.1 is the internal envelope and validation contract only. Its canonical specification, schema, validator, and baseline tests are byte-identical across the standalone TIIS baseline (Draft PR #68), the factory conversation adapter lane (Draft PR #69), and the TRADIX tooling adapter lane (Draft PR #70). This avoids three competing definitions of the same protocol.

### TRADIX tooling lane — Draft PR #70

The current consolidated tooling integration branch provides local, in-process adapters for:

- **Artifact Gateway:** project-bound read-only receipt metadata and extraction summary. No object download or artifact bytes.
- **Tool Catalog:** read-only `get`, `list`, and `history`. Registration and lifecycle mutations remain disabled until durable idempotency and audit controls exist.
- **Tool Adapter Contract:** typed TIIS invocation/result codec only. It does not execute tools, create workers, start sandboxes, schedule jobs, or invoke a shell.

Latest recorded CI for PR #70: run `44732000618`, completed successfully with 104 tests passed. This is local contract evidence, not a production transport or security claim.

### Factory conversation lane — Draft PR #69

A separate integration branch adapts the existing factory conversation domain message to the TIIS envelope. The outer TIIS sender/recipient remain authenticated component identities; the inner factory actor remains domain payload data. Project-scope authorization is a separate fail-closed policy.

Latest recorded CI for PR #69: run `44730132944`, completed successfully with 116 tests passed. This adapter maps and validates messages; it does not provide a transport, persistence, outbox, broker, or live model connection.

### Draft PR overlap and merge discipline

- PR #70 is the consolidated tooling-adapter lane.
- PR #71 and PR #73 are earlier/narrower Tool Catalog TIIS adapter variants. They overlap with PR #70 and must not be merged in addition to it without a deliberate reconciliation.
- PR #68 is the standalone TIIS 0.1 contract baseline. Its canonical TIIS artifacts are byte-identical to the copies carried by PRs #69 and #70.
- These branches have different dependency bases. Their PR bases must not be changed or rebased automatically to manufacture a linear history.

### Remaining TIIS gates

The following remain deliberately unimplemented:

1. Approved authentication/credential profiles for each deployment class.
2. A reviewed transport binding and component-principal lifecycle.
3. Durable replay/idempotency storage for state-changing operations.
4. Durable producer outbox and consumer inbox/checkpoint where loss is unacceptable.
5. Tamper-evident audit records and retention/export controls.
6. Real component-to-component failure-injection and end-to-end conformance.
7. Production security review and owner approval.

Until these gates pass, the adapters remain local prototypes. TIIS does not authorize a live endpoint, network listener, production write, or deployment.


## 8. Ordered delivery and acceptance record

| Stage | Draft PR | Scope | Latest recorded validation | Dependency/merge rule |
|---|---:|---|---|---|
| TIIS contract baseline | #68 | TIIS 0.1 specification, schema, validator, baseline tests | 102 tests passed; run `44729173799` | Standalone review evidence; same TIIS artifacts are carried byte-identically by #69 and #70. Do not merge separately on top of #70. |
| TRADIX factory adapter | #69 | Factory conversation ↔ TIIS adapter and project-scope authorization | 116 tests passed; run `44730132944`; two factory-specific workflows also succeeded | Separate factory-runtime integration lane; retain its own base and dependency review. |
| TRADIX tooling adapters | #70 | Artifact Gateway, Tool Catalog, Tool Adapter Contract TIIS adapters | 104 tests passed; run `44740384935` | Primary TIIS/TRADIX tooling lane and base for #77. |
| BRIDEX engineering plane | #77 | Independent draft scaffold, manifest validation, deterministic package, verification | 27 tests passed; run `44742859047`; shared repository tests also passed | Stacked on #70. One canonical `bridex-engine` package; do not merge parallel #72/#74 packages. |
| OBIS reference/conformance | #78 | Python/Go reference peers, TLS 1.3 mTLS candidate, bidirectional loopback tests | 57 Python tests + Go peer tests passed; run `44744149965`; 104 TRADIX tests passed in run `44744149964` | Stacked on #77. Older #75/#76 candidates are deferred; no production approval. |

### Merge discipline

No PR in this sequence has been merged or promoted. The intended review order is:

1. Review and accept the primary TIIS/TRADIX tooling lane (#70), after its existing dependency base is reviewed.
2. Review and accept BRIDEX Engine (#77) on top of #70.
3. Review and accept OBIS reference/conformance (#78) on top of #77.
4. Review the factory conversation adapter (#69) on its own factory-runtime dependency chain.

PR #68 is a standalone TIIS contract baseline whose artifacts are identical to those in #69/#70. PRs #71/#73 overlap the consolidated tooling lane. PRs #72/#74 contain parallel BRIDEX package implementations. PRs #75/#76 contain earlier OBIS TLS candidates. These are review evidence, not additional merge steps.

The successful tests establish local contract, package, and loopback conformance only. They do not authorize production transport, real peer credentials, external endpoints, deployment, or live data exchange.
