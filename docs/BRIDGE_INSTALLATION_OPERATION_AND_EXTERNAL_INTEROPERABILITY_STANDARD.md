# Bridge Installation, Operation, Separation, and External Interoperability Standard

**Document ID:** BRIDEX-STD-OPS-001  
**Version:** 1.0.0  
**Status:** Proposed governing standard; pending owner approval  
**Authority:** Project owner  
**Scope:** Every project-owned or tool-owned Bridge generated, packaged, operated, or maintained using BRIDEX, including Bridges separated from the originating ecosystem.

Normative terms **MUST**, **MUST NOT**, **SHOULD**, and **MAY** express requirements, prohibitions, recommendations, and options.

## 1. Purpose and governing principle

A Bridge is a separately identifiable integration tool built for a designated project or tool. That project/tool owns it. BRIDEX supplies the reusable engineering method, generic foundations, generation, packaging, and conformance tooling; it is not the owner, mandatory runtime, central gateway, or permanent operator.

A Bridge MUST remain usable after its owner leaves, is removed from, or otherwise separates from the originating ecosystem. It MUST be capable of connecting, under explicit authorization, to applications, services, tools, and independently operated Bridges outside that ecosystem. This is a design and acceptance requirement, not a promise of automatic compatibility with every external product.

This standard operationalizes [Portfolio-Wide Independence and Bridge Standard](PORTFOLIO_INDEPENDENCE_AND_BRIDGE_STANDARD.md), [BRIDEX Ownership, Control, and Portability Policy](BRIDEX_OWNERSHIP_AND_PORTABILITY_POLICY.md), and [BRIDEX Architecture](BRIDEX_ARCHITECTURE.md).

## 2. Ownership and authority

The project/tool whose resources, data, or capabilities the Bridge is authorized to expose owns the Bridge. Where a Bridge is dedicated to a tool's own integration boundary, that tool's designated owning project owns it. The external provider hosting an account/resource does not become the Bridge owner merely by hosting it.

The ownership record MUST distinguish:
- **Owner:** final authority over identity, source/package, configuration, release, permissions, lifecycle, transfer, and retirement.
- **Operator:** runs the deployed instance under the owner's authority.
- **Maintainer:** performs approved maintenance and releases.
- **Peer/consumer:** independently identified system authorized to consume specified capabilities; consumption does not transfer ownership.

BRIDEX MUST NOT be recorded as owner. A receiving project owns its own ingress adapter, validation, authorization, and data-acceptance boundary, not the source-side Bridge. Separate Bridges at project boundaries are the default. A shared multi-project Bridge requires prior written joint-ownership/governance approval by every affected owner, with enforceable per-project identity, credentials, scopes, data isolation, audit, exit, and replacement rights.

The owner MUST possess complete source or an independently buildable package and, subject to third-party licenses, the rights to build, run, inspect, modify, fork, transfer, appoint/replace operators and maintainers, and continue development without BRIDEX/TRADIX.

## 3. Independent connection capability

A Bridge MUST be a peer integration endpoint, not an ecosystem-internal connector that becomes useless outside its original portfolio. It MUST support:
1. Authorized applications and tools owned by the same project.
2. Authorized applications, services, and tools outside the originating ecosystem.
3. Bridge-to-Bridge communication with independently owned implementations.
4. Peer, endpoint, transport, and adapter replacement without transferring ownership or rebuilding the Bridge from zero.
5. Operation without mandatory calls to TRADIX, BRIDEX, a TRADIX registry, relay, broker, identity provider, catalog, or license server.

OBIS is the default external interoperability contract. A separately documented, versioned, replaceable adapter MAY be used where a target cannot speak OBIS directly. TIIS is restricted to explicitly authorized TRADIX-internal integration; a TIIS adapter MUST be optional and removable/disableable without breaking external OBIS operation.

Universal plug-and-play compatibility MUST NOT be claimed. Each target requires a declared protocol/adapter version, capability mapping, security profile, peer authorization, and conformance evidence.

## 4. Identity, trust, authorization, and connection control

Every Bridge MUST have a stable Bridge ID, implementation version, owner identity, and separately recorded operator identity. Every peer MUST have its own identity and trust decision. A TRADIX identity or registration MUST NOT be a prerequisite for trusting an otherwise authorized external peer.

For every connection, the owner MUST explicitly approve peer identity/trust method, allowed capabilities and resource/data scopes, access direction, data classification/retention, authentication and authorization profile, expiry, renewal, revocation, and incident response.

Authentication is not authorization. Access MUST be deny-by-default and least-privilege. Credentials and secret values MUST remain under the owning project's control in an owner-controlled secret facility or protected local runtime. They MUST NOT appear in public manifests, catalogs, logs, or exported non-secret metadata. Revoking one peer MUST NOT require disabling unrelated peers.

## 5. Standalone installation and runtime

A released Bridge MUST be installable and operable using its delivered package and documented prerequisites, without requiring an online BRIDEX/TRADIX service, repository, registry, account, credential, build server, or license check at runtime.

The release package MUST include, as applicable:
- Complete source or independently buildable artifacts and integrity hashes.
- Build/install instructions for declared supported environments.
- Runtime/dependency versions, lockfiles, license inventory, and SBOM or equivalent.
- Configuration schema and safe non-secret example configuration.
- OBIS specification/schema versions and required adapter contracts.
- Owner/operator record and assignment evidence.
- Health, logging, audit, backup, restore, upgrade, rollback, export, replacement, and retirement instructions.
- Unit, security, compatibility, interoperability, and independence test results.

The supported platform matrix MUST declare OS, architecture, runtime/container requirements, network/storage requirements, and optional infrastructure. A container or cloud account MUST NOT be mandatory unless explicitly required by the approved use case and documented as a replaceable deployment choice where feasible.

Installation MUST fail safely when required configuration, owner attestation, trust material, or permissions are missing. A generated scaffold or package manifest alone is not an installed or operational Bridge.

## 6. Separation and exit guarantee

The owner MUST be able to separate the Bridge from TRADIX, BRIDEX, or any originating ecosystem without losing essential functionality or control. A separation test MUST demonstrate:
1. Source/package and owner-controlled configuration can be exported.
2. The package can be built/installed in a clean environment outside the originating ecosystem.
3. The Bridge starts and performs approved functions while TRADIX/BRIDEX services, repositories, registries, relays, and credentials are unavailable.
4. External peer connections can be re-established using owner-controlled identities, trust material, and documented configuration.
5. Peer grants can be retained, narrowed, revoked, or re-issued individually by the owner.
6. Logs/audit evidence and permitted operational state can be exported in documented formats.
7. The owner can appoint a different operator/maintainer, fork or replace implementation components, and continue operation.
8. No hidden online license, telemetry, central identity, proprietary build service, or factory callback blocks normal operation.

Leaving the ecosystem MUST NOT automatically revoke unrelated external peer grants, erase owner data, or disable the Bridge. Security-driven revocation must be an explicit owner-controlled action or a separately documented legal/security requirement.

## 7. Reliability, safety, and operational controls

Each Bridge MUST define bounded timeouts, retry rules, idempotency behavior, cancellation, partial-failure handling, and unknown-outcome reconciliation appropriate to its operations. It MUST define health/readiness semantics and MUST NOT report unavailable upstream sources as zero values or successful empty results.

The runtime MUST validate peer identity, schema, payload size, freshness/expiry, replay behavior, authorization, and capability scope. It MUST NOT expose unrestricted shell, script, command, filesystem, or arbitrary network execution through generic operations.

Logs/audit evidence MUST identify Bridge, owner, peer, capability, decision, timestamp, and outcome while excluding secrets and minimizing sensitive payload capture. Backup/restore and retention remain under owner control.

## 8. Lifecycle states and evidence

These states MUST NOT be conflated:
1. **Designed** — purpose, owner, peers, contracts, and scope specified.
2. **Generated** — source/scaffold produced by BRIDEX tooling.
3. **Packaged** — independently exportable artifact and documentation produced.
4. **Owner-attested** — owner assignment and release authority recorded.
5. **Installed** — installed in a declared environment.
6. **Deployed** — configured instance placed in its target environment.
7. **Active** — health and authorized operations observed.
8. **Interoperability-tested** — successful tests with an independent peer/target.
9. **Separation-tested** — external operation proven without BRIDEX/TRADIX.
10. **Production-accepted** — applicable security, reliability, portability, owner-approval, and operational gates passed.
11. **Revoked/Retired** — access or lifecycle ended under owner-controlled procedure.

Every status claim MUST link to evidence containing Bridge ID, owner, operator, source commit/package hash, environment, peer IDs, protocol/schema/security profile versions, approved scopes, test results, timestamp, and approving authority. CI success, generated scaffolds, or loopback tests alone MUST NOT be described as deployed, externally interoperable, separation-tested, or production-accepted.

## 9. Mandatory acceptance matrix

| Gate | Required evidence |
|---|---|
| Ownership | Explicit owner/operator/maintainer record and owner attestation |
| Package autonomy | Clean build/install from exported package |
| Runtime independence | Operation with BRIDEX and TRADIX unavailable |
| External interoperability | Connection to an independently operated non-TRADIX peer |
| Separation | Reinstallation/reconfiguration outside originating ecosystem |
| Security | Peer authentication, scoped authorization, denial, revocation, secret isolation |
| Compatibility | Declared supported and rejected protocol/schema combinations |
| Reliability | Timeout, retry, cancellation, replay/idempotency, partial-failure behavior |
| Portability | Export/restore, operator replacement, fork/replace path |
| Lifecycle | Upgrade, rollback, backup/restore, decommissioning |
| Owner acceptance | Recorded approval of deployed scope and environment |

The test peer MUST be independent of BRIDEX runtime services. A BRIDEX reference implementation MAY be a test fixture, but fixture success is not proof of a live owner-operated Bridge or production deployment.

## 10. Exceptions and change control

Any exception MUST be explicit, written, owner-approved, narrowly scoped, time-bounded or reviewable, and accompanied by risks and compensating controls. Convenience, repository placement, or an existing implementation does not create an exception.

Changes to ownership, external interoperability, mandatory runtime dependencies, or separation rights require a versioned amendment and explicit project-owner approval.

## 11. Current implementation status

This standard defines requirements; it does not certify current Bridge implementations. Current BRIDEX/OBIS reference implementations and BRIDEX Core are development foundations. Production transport security, complete conformance, clean-environment deployment, owner-attested operational Bridge instances, external target integrations, and separation-test evidence must be assessed separately. No production Bridge or live external connection is implied.

## 12. Governing statement

**Every Bridge is an independently owned integration tool for its designated project or tool. Its owner controls it, may connect it to explicitly authorized compatible applications/systems, and may separate it from the originating ecosystem without losing ownership or essential operation. BRIDEX builds the engineering foundation; it does not own, centrally control, or permanently mediate project Bridges.**
