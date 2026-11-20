# BRIDEX — Bridge Ownership, Control, and Portability Policy

**Document ID:** BRIDEX-GOV-OWN-001  
**Status:** GOVERNING / MANDATORY  
**Version:** 1.1.0  
**Effective date:** 2026-11-20  
**Authority:** Project owner  
**Scope:** BRIDEX and every Bridge generated, packaged, maintained, or governed using the BRIDEX method

## 1. Purpose

This policy separates three matters that must never be conflated:

1. **BRIDEX independence:** BRIDEX is an independent project and engineering tool for designing, generating, testing, packaging, and evolving Bridge tools.
2. **Bridge-instance ownership:** Each project-specific Bridge is owned by the portfolio project whose resources, data, or capabilities it is authorized to expose. BRIDEX never owns a project Bridge.
3. **Bridge portability and interoperability:** A Bridge must remain operable, modifiable, transferable, and adaptable to other systems after separation from BRIDEX and TRADIX.

The purpose is to let every project retain control of its integration capability and leave or replace any ecosystem without losing the Bridge needed to connect to other systems.

## 2. Binding ownership rule

BRIDEX is the generator and engineering-method provider. It is **never the owner** of a project Bridge instance.

For this policy, the source/resource-owning project is the portfolio project that owns, administers, or has delegated authority over the relevant source account, resource, data, or capability and authorizes the Bridge to access or expose it; it is not the external SaaS/cloud provider that hosts the resource. Ownership of each Bridge instance must be explicitly assigned and recorded before release. The owner must be that source/resource-owning project. For a project-specific Bridge, ownership cannot be assigned to BRIDEX, the generator, the receiving project, a hosting provider, or an unrelated entity.

A project may appoint another party as operator or maintainer under its control, but that appointment does not transfer ownership. Where an integration requires Bridges on both sides, each project owns its own boundary Bridge. A shared multi-project Bridge is prohibited unless every affected project owner explicitly approves a written joint-ownership agreement defining governance, project isolation, credentials, data scopes, exit, and replacement rights. BRIDEX is never the default joint owner.

The fact that BRIDEX generated, packaged, tested, hosted during development, or maintained a Bridge does not confer ownership on BRIDEX. The source/resource-owning project retains ownership. A receiving project owns its own ingress adapter and acceptance boundary, not the other project's source-side Bridge.

Where ownership and operation are split, the record must separately identify the owner, operator, maintainer, and parties authorized to approve changes.

## 3. Minimum rights of the designated owner

Subject to third-party and open-source license obligations, the Bridge owner must have the practical and legal rights needed to control the Bridge independently, including:

- Access to and possession of the complete source code or a complete, independently buildable source package.
- Access to build instructions, dependency manifests, schemas, protocol specifications, tests, and release artifacts required to reproduce and operate it.
- The right to run, configure, inspect, maintain, repair, extend, and modify the Bridge.
- The right to fork the implementation and continue development independently.
- The right to appoint or replace developers, operators, maintainers, hosting providers, and other service providers.
- The right to transfer the Bridge and its maintainable source package to another owner or operator, subject to applicable law and third-party licenses.
- The right to replace BRIDEX-generated components or protocol adapters without losing ownership of the Bridge or being forced to use BRIDEX services.
- The right to export the Bridge's configuration, permitted operational records, audit/evidence records, and lifecycle data in documented formats.

A delivery that provides only a hosted endpoint, opaque binary, or generator-dependent project is not sufficient to satisfy this policy unless the owner has explicitly approved that limited arrangement as a documented exception.

## 4. Portability and exit requirements

Every released Bridge must be capable of being separated from BRIDEX and TRADIX without losing its essential operation. It is built for its designated project/tool and must remain capable of connecting to authorized applications, services, and independent systems outside the originating ecosystem. Separation must not turn it into an unusable ecosystem-only connector.

The release package must include or identify:
- Source and reproducible build/deployment instructions.
- OBIS specification and the exact supported protocol/schema versions.
- All required non-secret configuration schemas and example configurations.
- Replaceable transport and vendor-specific adapters, with their declared contracts.
- Dependency and license inventory.
- Tests and conformance evidence.
- Operational, backup, restore, upgrade, rollback, migration, and decommissioning documentation.
- Export procedures for owner-controlled state and records.

No essential runtime path may require:
- A live BRIDEX generator or license server.
- A TRADIX repository, service, catalog, registry, relay, broker, or identity provider.
- A BRIDEX-controlled credential, signing service, or remote configuration service.
- A proprietary build or deployment service that the owner cannot replace, unless explicitly approved as a time-bounded exception.

Secrets must not be embedded in exported source or ordinary configuration packages. Secret references and migration procedures must be documented so the owner can provision equivalent credentials under its own control.

## 5. Interoperability and adaptation

OBIS is the independent interoperability contract carried by each Bridge for communication with external peers and other independently operated Bridges.

A Bridge must not be designed so that its only meaningful integration target is TRADIX, BRIDEX, or one portfolio product. It must use documented, versioned contracts and replaceable adapters so its owner can connect it to other systems.

This does not promise automatic compatibility with every system. A new target may require a new adapter, mapping, authentication profile, or conformance test. The architectural requirement is that these additions can be made without surrendering ownership, rebuilding the Bridge from zero, or introducing a mandatory dependency on the original ecosystem.

The owner must be able to:
- Add or replace a peer connection through documented interfaces.
- Add or replace a transport/protocol adapter where needed.
- Change endpoint, identity, mapping, and authorization configuration without modifying unrelated Bridge instances.
- Validate a new integration using the published conformance suite or an equivalent independently runnable test set.

## 6. BRIDEX responsibilities and limits

BRIDEX is responsible for maintaining the common engineering method, reusable generic foundations, generation templates, packaging conventions, security checks, and conformance tooling. It is not an owner, portfolio-wide operator, or mandatory control plane for project Bridge instances.

BRIDEX may provide optional maintenance or support for a Bridge only under an explicit agreement with its owner. Such support does not transfer ownership or create an unavoidable runtime dependency.

BRIDEX must not:
- Claim ownership solely because it generated a Bridge.
- Retain exclusive control of source, build, signing, release, or operational credentials for an owner-assigned Bridge.
- Make continued operation depend on BRIDEX availability.
- Prevent the owner from forking, modifying, transferring, replacing, or independently maintaining the Bridge.
- Centralize project-specific secrets, payloads, or business logic in the BRIDEX engineering plane.

## 7. Required ownership record

Every Bridge instance must have a machine-readable and human-readable ownership record containing at least:

- Bridge ID, name, and implementation version.
- Designated owner and evidence/record of assignment.
- Operator and maintainer, if different.
- Rights and license applicable to the Bridge source and package.
- Third-party components and their licenses.
- Source/package location and export procedure.
- Supported OBIS and adapter versions.
- Peer systems and approved integration scopes.
- Configuration and data ownership boundaries.
- Transfer, replacement, and exit procedure.
- Conformance evidence and release date.

An absent or ambiguous owner is a release blocker, not an invitation to infer ownership.

## 8. Acceptance tests

A Bridge is not accepted as independently portable until tests demonstrate that:

1. The designated owner can obtain the complete source/package and required documentation.
2. The owner or its chosen operator can build, deploy, and run it without BRIDEX or TRADIX runtime services.
3. OBIS communication continues when BRIDEX and TRADIX are unavailable.
4. A new peer or adapter can be configured or implemented using documented interfaces.
5. The Bridge can be forked or maintained in a separate repository and build environment.
6. Owner-controlled configuration and permitted operational records can be exported and restored.
7. BRIDEX-specific services, credentials, registries, and license checks are not hidden runtime prerequisites.
8. Third-party license restrictions and required notices are included in the package.

Unit tests alone do not prove ownership, portability, or interoperability.

## 9. External application connectivity and separation

A project Bridge is not restricted to connecting only to TRADIX portfolio projects. Subject to its owner's authorization, it must support documented connections to independent third-party applications, services, tools, and independently operated Bridges. OBIS is the default external contract; any alternative adapter must be explicit, versioned, replaceable, and independently testable. TIIS remains optional and limited to authorized TRADIX-internal integration.

The owner must be able to take the Bridge, its source/package, non-secret configuration, schemas, and operational documentation into a separate repository, build environment, operator, or ecosystem; install and operate it there; and configure new authorized peers without BRIDEX/TRADIX services. This is portability and adaptability, not a claim of automatic compatibility with every application. Each target integration requires its own protocol mapping, peer trust, scopes, and conformance evidence.

The detailed installation, operation, separation, and external interoperability requirements are defined in [Bridge Installation, Operation, Separation, and External Interoperability Standard](BRIDGE_INSTALLATION_OPERATION_AND_EXTERNAL_INTEROPERABILITY_STANDARD.md).

## 10. Relationship to governing architecture

This policy supplements and clarifies:
- [Portfolio-Wide Independence and Bridge Standard](PORTFOLIO_INDEPENDENCE_AND_BRIDGE_STANDARD.md)
- [Foundational Architecture Charter](FOUNDATIONAL_ARCHITECTURE_CHARTER.md)
- [BRIDEX Project Dossier](../projects/BRIDEX/README.md)
- [BRIDEX Architecture](BRIDEX_ARCHITECTURE.md)

Where earlier wording could be read as assigning ownership to the generator or treating owner/operator as a single role, this policy controls: the source/resource-owning project is the owner, BRIDEX is never the owner, and the owning project must receive the rights and portable deliverables defined here.

## 10. Version history

- **1.2.0 (2026-11-20):** made external application connectivity and continued usability after ecosystem separation explicit owner rights and Bridge release requirements; added the dedicated installation/operation/separation standard.
- **1.1.0 (2026-11-20):** clarified and made mandatory that every project-specific Bridge is owned by the project whose resources, data, or capabilities it exposes; BRIDEX is never the owner. Added source-side/receiving-side separation and explicit joint-ownership exception controls.

## 11. Governing statement

**BRIDEX owns and evolves only its independent engineering/generation project. The project/tool for which a Bridge is built owns and controls that Bridge instance. The owner may connect it to authorized independent applications and systems and may separate it from the originating ecosystem without losing ownership or essential operation. BRIDEX never owns or permanently mediates project Bridges.**
