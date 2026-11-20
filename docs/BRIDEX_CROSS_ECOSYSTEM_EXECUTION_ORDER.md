# BRIDEX / TRADIX / OBIS / TIIS — Cross-Ecosystem Execution Order

**Document ID:** BRIDEX-EXEC-ORDER-001  
**Status:** Proposed execution control; pending owner review  
**Applies to:** TRADIX, BRIDEX, every generated Bridge, and every connected project/application  
**Purpose:** Prevent integration drift, incompatible contracts, hidden dependencies, and late-stage rework.

## 1. Binding execution rule

Work must proceed in dependency order, not by whichever project appears most ready. No downstream implementation may silently invent, fork, or assume an upstream interface. Every phase has an explicit exit gate. If a gate fails, dependent work pauses; unrelated independent work may continue.

The governing architecture remains:
- TRADIX is the portfolio factory/toolbox and builds portfolio tools, while completed tools operate independently.
- BRIDEX is the specialist engineering/generation system for independent Bridge tools.
- Each generated Bridge has its own identity, owner/operator, source/package, configuration, permissions, runtime, and lifecycle.
- OBIS is the external, vendor-neutral interoperability contract.
- TIIS is restricted to authorized TRADIX-internal integration. A Bridge's TIIS-facing adapter is optional and must not be required for external OBIS operation.
- Connected applications and projects remain independent peers and retain control of their own APIs, data, credentials, permissions, and business logic.

## 2. Required execution sequence

### Phase 0 — Establish the approved architecture baseline
1. Review and approve the ecosystem master map, Foundational Architecture Charter, portfolio-wide independence/Bridge standard, BRIDEX architecture, ownership/portability policy, and the separate OBIS and TIIS specifications.
2. Resolve contradictions between governing documents before implementation proceeds.
3. Record the exact approved document versions and hashes used by each implementation.
4. Keep draft documents explicitly marked as drafts; a document in a PR is not an approved production contract.

**Exit gate:** one consistent, owner-approved architecture baseline with clear project boundaries, ownership, data boundaries, and protocol responsibilities.

### Phase 1 — Freeze protocol and interface contracts
1. Define OBIS core semantics, identity model, version negotiation, envelope, capability model, authorization semantics, errors, expiry, reliability, and compatibility rules.
2. Define TIIS separately for TRADIX-internal components; do not import TIIS assumptions into OBIS.
3. Publish versioned normative schemas and canonicalization rules.
4. Define transport bindings and security profiles as separately versioned contracts.
5. Create a compatibility matrix covering protocol version, schema version, security profile, transport binding, and required/optional capabilities.
6. Define explicit rules for unsupported versions, unknown required fields/features, safe downgrade prevention, deprecation, and migration.

**Exit gate:** implementers can build independently from the published contracts without relying on undocumented TRADIX or BRIDEX behavior.

### Phase 2 — Establish TRADIX internal integration boundaries
1. Identify which components are truly TRADIX-internal and therefore use TIIS.
2. Specify each internal component's exposed/consumed interfaces, identity, permissions, data classification, and failure boundary.
3. Reuse Artifact Gateway, Tool Catalog, or Tool Adapter Contract only where their actual implemented contracts fit.
4. Treat those components as optional development/packaging/catalog/invocation support, not as OBIS, Bridge identity, peer trust, or mandatory runtime infrastructure.
5. Respect the existing dependency chain if those components are reused: PR #45 → PR #46 → PR #47. Recheck current PR status and acceptance evidence before depending on any of them. Do not bypass their declared base dependencies.

**Exit gate:** TRADIX internal contracts are independently testable, and every proposed reuse has a replaceable interface and a documented non-dependency path.

### Phase 3 — Build and validate the generic BRIDEX / OBIS foundation
1. Implement the generic Bridge Core without destination-specific business logic.
2. Complete OBIS peer behavior against the frozen schemas and protocol contract.
3. Finalize and independently review the production security profile, trust-anchor model, credential issuance/rotation/revocation, and authorization enforcement.
4. Implement durable replay/idempotency, audit/evidence persistence, bounded retries, cancellation, and outcome reconciliation.
5. Run positive and negative conformance tests, including unauthorized peer/scope, stale/replayed messages, unsupported versions, malformed payloads, timeout, partial failure, and revocation.
6. Demonstrate interoperability with a separately implemented peer, preferably in a second language and by an independent implementation path.

**Exit gate:** the generic foundation passes protocol, security, reliability, and cross-implementation tests. A loopback-only reference test or successful package build is not sufficient.

### Phase 4 — Build the Bridge generation and release pipeline
1. Generate a standalone Bridge from generic BRIDEX foundations plus isolated destination-specific configuration/adapters.
2. Assign and record the Bridge ID, owner, operator, maintainer, supported contracts, peer identities, scopes, and lifecycle.
3. Package source or independently buildable artifacts, schemas, dependency/license inventory, reproducible build/deploy instructions, configuration templates, tests, evidence, migration, rollback, and export procedures.
4. Prove destination-specific changes do not alter the generic core or unrelated Bridge instances.
5. Prove the generated Bridge can be built, deployed, operated, maintained, and exported without BRIDEX/TRADIX services, repositories, registries, credentials, or online license checks.

**Exit gate:** a generated Bridge is a separately usable and maintainable product, not merely a module or an entry in a catalog.

### Phase 5 — First controlled application pilot
1. Select one low-risk integration only after the generic Bridge and protocol gates pass.
2. The target project first publishes its own approved interface contract, capability list, data classification, permission model, and test fixtures.
3. The target project explicitly approves the Bridge identity, owner/operator, data scope, and capabilities.
4. Implement only the destination-specific adapter and mappings in that Bridge instance.
5. Test both directions where required, schema/version compatibility, least privilege, denial paths, revocation, idempotency, failure isolation, and audit evidence.
6. Run the pilot with TRADIX and BRIDEX unavailable to prove the runtime path is independent.
7. Keep the pilot isolated from unrelated projects, accounts, data, and credentials.

**Exit gate:** end-to-end interoperability and independent operation are demonstrated with recorded evidence and explicit project-owner acceptance.

### Phase 6 — Portfolio rollout and controlled evolution
1. Generate additional Bridge instances one project at a time; do not copy pilot-specific logic into the generic core.
2. Maintain a portfolio compatibility matrix and per-Bridge conformance record.
3. For every protocol, schema, security-profile, or adapter change, run regression tests against all declared supported versions and affected Bridge instances.
4. Use explicit version negotiation and documented migrations; never silently break an already released Bridge.
5. Roll out with staged deployment, rollback, revocation, and export/replacement plans.
6. Re-run independence and cross-project tests after material changes.

**Exit gate:** each Bridge and connected application passes its own acceptance gates. Portfolio-wide status must not be inferred from one successful pilot.

## 3. Mandatory integration test matrix

Every integration must test, as applicable:

- Protocol and schema compatibility, including supported and unsupported version combinations.
- Peer identity, authentication, authorization, scope narrowing, and revocation.
- Data minimization, project/source isolation, and forbidden cross-project access.
- Positive request/response, structured errors, correlation, expiry, and malformed messages.
- Replay, idempotency, retries, timeouts, cancellation, partial failure, and unknown outcomes.
- Audit/evidence attribution and secret/personal-data leakage prevention.
- Destination-specific change isolation from BRIDEX core and unrelated Bridges.
- Operation with TRADIX unavailable and BRIDEX unavailable.
- Export, restore, upgrade, rollback, replacement, and decommissioning.
- Optional TIIS adapter removal without breaking OBIS external communication.

## 4. Current known baseline and open gates

At the time this document is drafted:
- PR #42 is a consolidated Draft review branch and has not been merged.
- PR #66 content was synchronized into PR #42 at content level; the two branch histories were not merged.
- CI run #1014 passed its recorded Python tests, wheel builds, isolated installs, and packaged-schema smoke checks.
- Those CI results do not prove production TLS/mTLS, durable replay/idempotency, production audit persistence, second-language interoperability, or the combined ECOSCAN-adapter-to-OBIS-peer path.
- The OBIS 0.1 and TIIS 0.1 documents remain draft baselines, not production 1.0 contracts.
- Existing TRADIX component PR dependencies must be rechecked before reuse; their presence in documentation does not prove they are merged or production-ready.

## 5. Stop conditions

Pause dependent implementation when:
- A governing contract is ambiguous, contradictory, or unapproved.
- An implementation depends on an undocumented interface or an unmerged dependency.
- A Bridge requires BRIDEX/TRADIX runtime services for normal external operation.
- A connected project has not approved the exposed capabilities, data scope, or peer identity.
- Compatibility, security, or isolation tests fail.
- A change would silently break an already released contract or Bridge.

No production connection, credential provisioning, deployment, PR merge, or project-wide rollout is authorized by this execution-order document. Those actions require their own explicit approval.

## 6. Governing references

- `docs/ECOSYSTEM_MASTER_MAP.md`
- `docs/FOUNDATIONAL_ARCHITECTURE_CHARTER.md`
- `docs/PORTFOLIO_INDEPENDENCE_AND_BRIDGE_STANDARD.md`
- `docs/BRIDEX_ARCHITECTURE.md`
- `docs/BRIDEX_EXISTING_COMPONENT_INTEGRATION_MAP.md`
- `docs/OBIS_SPECIFICATION.md`
- `docs/TIIS_SPECIFICATION.md`
- `projects/BRIDEX/README.md`
