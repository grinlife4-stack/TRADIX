# Ecosystem Master Map — TRADIX Factory and Independent Systems

**Document ID:** ECOSYSTEM-MAP-001  
**Status:** Proposed governing portfolio rule; pending owner review  
**Canonical location:** `grinlife4-stack/TRADIX/docs/ECOSYSTEM_MASTER_MAP.md`

## 1. Core model

The ecosystem has independent projects and systems, and TRADIX is the permanent factory that builds and develops their tools and products.

- **TRADIX is the factory and the toolbox.** It designs, builds, tests, documents, packages, secures, and prepares every portfolio tool and product. It continuously develops its own production capabilities and remains available to build new tools and improve existing ones.
- **A tool is not the toolbox.** Once built, each tool has its own identity, purpose, codebase or bounded source, configuration, data, lifecycle, and operating responsibility.
- **The toolbox is not a runtime dependency.** A completed tool can be installed, operated, maintained, moved, or replaced without carrying or running TRADIX.
- **The toolbox remains permanent.** TRADIX continues to exist and develop even while individual tools are being used independently.
- **The factory relationship does not create operational control.** TRADIX building a tool does not give TRADIX authority over the tool's domain, records, decisions, credentials, or day-to-day operation.
- **Tools are available, not compulsory.** A project uses a tool when it fits its needs; it does not have to run every tool or use TRADIX at runtime.

**Short rule: TRADIX builds and continuously develops the toolbox. Every completed tool remains an independent tool.**

## 2. The toolbox analogy

TRADIX is like a workshop that builds and maintains a toolbox. The toolbox helps identify, organize, document, version, and retrieve the tools. A wrench remains a wrench after it is made: the mechanic does not need to carry the workshop to use it.

Applied to the ecosystem:

- TRADIX creates all tools in the portfolio through its engineering lifecycle.
- TRADIX keeps developing its own factory capabilities and the toolbox/catalogue.
- Each tool is separately identifiable and can be used without TRADIX being running or reachable.
- The tool may be listed, documented, versioned, tested, and maintained through TRADIX without surrendering its identity or operational independence.
- TRADIX may build a new version or replacement, but changes to the factory must not silently break tools already delivered.
- Tool use does not imply that all tools must be installed together or that they share one runtime, database, credential store, or deployment.

## 3. Distinguish projects, factory, and tools

### 3.1 TRADIX

TRADIX is the portfolio's permanent product-and-tool factory. Its responsibilities include:

- Building every portfolio product and tool from approved requirements.
- Continuously improving its own architecture, engineering methods, templates, test systems, security controls, packaging, release processes, and reusable foundations.
- Keeping a discoverable catalogue and documentation for tools it has built.
- Maintaining versioned interfaces and migration paths where tools use shared capabilities.
- Supporting authorized upgrades without acquiring ownership of the systems it builds.

TRADIX is not automatically the owner, operator, runtime host, or mandatory dependency of any completed tool or product.

### 3.2 Independent products and projects

Each product/project has its own purpose, roadmap, acceptance decisions, records, data, assets, accounts, credentials, finances, and operating boundary. Examples include NEXORA, MegaMarket, AAECN, the Trading Intelligence Platform, XENORA AI, BRIDEX, and other explicitly registered projects. BRIDEX is an independent specialist project/tooling system for generating and validating portable Bridge tools; its placement in the TRADIX portfolio does not make its runtime or generated Bridges dependent on TRADIX.

A repository folder or shared development workspace does not merge project identities or ownership.

### 3.3 Independent tools built by TRADIX

Tools have their own identity and operating boundary even though TRADIX builds and catalogues them. Current examples include:

- **EXVARLI:** the independent multi-project financial-management system. It provides financial management and oversight capabilities while preserving each project's separate financial perimeter, accounts, funds, ledgers, permissions, and records. Its governing specification is `docs/projects/EXVARLI_FINANCIAL_ARCHITECTURE.md`.
- **ECOSCAN:** the independent ecosystem resource and infrastructure monitoring system. It measures registered technical/storage resources at whole-ecosystem, project, subsystem, or individual-source scope, only when requested or when an explicitly enabled schedule is due. Its governing specification is `docs/tools/ECOSCAN_SPEC.md`, proposed MVP/implementation boundary is `docs/tools/ECOSCAN_IMPLEMENTATION_PLAN.md`, ready-made capability audit is `docs/tools/ECOSCAN_READY_MADE_CAPABILITY_AUDIT.md`, draft threat model and acceptance matrix is `docs/tools/ECOSCAN_THREAT_MODEL_AND_ACCEPTANCE_MATRIX.md`, and versioned 0.1 contract schemas are under `standards/ecoscan/0.1/`.
- **BRIDEX:** the independent specialist Bridge engineering project/tool. It defines and maintains the repeatable method, generic foundations, packaging rules, and conformance tooling for generating independent Bridge instances. BRIDEX never owns project Bridge instances. Each Bridge is owned by the project whose resources, data, or capabilities it is authorized to expose. The project retains source, configuration, credentials, permissions, lifecycle, and replacement control. A receiving project owns its own ingress/validation boundary. Cross-project integrations use separately owned Bridges at each project boundary by default; shared Bridges require explicit written joint ownership approval from every affected project. All project-owned Bridges must remain operable without BRIDEX or TRADIX runtime dependencies. The governing dossier and specifications are maintained in `projects/BRIDEX/README.md` and the related `docs/BRIDEX_*.md` / protocol specification documents. The current executable OBIS Python peer is a loopback-only development prototype, not production security approval. Existing Artifact Gateway, Tool Catalog, and Tool Adapter boundaries are recorded in `docs/BRIDEX_EXISTING_COMPONENT_INTEGRATION_MAP.md`.

EXVARLI and ECOSCAN are peer tools in the TRADIX toolbox. Neither is a submodule, owner, or runtime dependency of the other. Neither requires TRADIX to be running when it performs its own authorized work.

BRIDEX is a specialist project/tooling system within the same independent portfolio model. Its role as Bridge generator does not make it the owner of each generated Bridge. A generated Bridge is a separately identifiable tool owned by the project whose resources or capabilities it exposes, with separately recorded operator and maintainer roles. BRIDEX does not own generated Bridges. The owning project retains source/package, modification and fork rights, transfer and export rights, and authority over credentials, permissions, release, operation, and retirement. OBIS is the independent external interoperability contract; TIIS applies only to authorized TRADIX-internal integration. The detailed contracts are maintained separately in `docs/OBIS_SPECIFICATION.md` and `docs/TIIS_SPECIFICATION.md`. Every Bridge is intended for its designated project/tool, remains owned and controlled by that owner, and must be connectable to explicitly authorized external applications and independent systems. Its owner must be able to separate it from the originating ecosystem, install and operate it independently, and reconfigure external peers without BRIDEX/TRADIX runtime participation. This is an explicit portability and acceptance requirement, not a claim of universal plug-and-play compatibility. See `docs/BRIDGE_INSTALLATION_OPERATION_AND_EXTERNAL_INTEROPERABILITY_STANDARD.md`.

## 4. Independence and separation rules

Every project and every completed tool retains its own boundary.

- A tool owns or controls only the records and configuration required for its own function, under its approved mandate.
- TRADIX's source catalogue may hold tool descriptions, versions, documentation links, build provenance, and compatibility metadata; it must not become the default store for tool runtime data or project secrets.
- No project data, financial records, accounts, wallets, credentials, customer records, or private assets may be merged merely because they use the same tool.
- Cross-project views must preserve source attribution and access permissions.
- A tool must expose export and replacement paths appropriate to its data and role.
- Stopping, deleting, replacing, or losing access to TRADIX must not stop a completed tool or erase its records.
- Stopping, deleting, or replacing one tool must not stop TRADIX, other tools, or any project.
- Shared interfaces are explicit, documented, versioned, and least-privilege. No hidden dependency is permitted.

## 5. Tool construction and lifecycle

TRADIX uses a repeatable lifecycle for every tool:

1. Define the real need, intended users, operating boundary, and acceptance criteria.
2. Check whether an existing tool already solves the need.
3. Specify the tool's independent identity, data ownership, access model, and runtime dependencies.
4. Design and build the tool.
5. Test functionality, security, isolation, portability, failure handling, and removal.
6. Document installation, configuration, operation, export, upgrade, rollback, and retirement.
7. Deliver/version the tool as an independent usable unit.
8. Maintain its catalogue entry and build provenance in TRADIX.
9. Develop later versions when authorized, without silently changing existing operational contracts.

A tool is not considered complete merely because its code exists or its tests pass. Its documented acceptance gates must be met.

## 6. Tool discovery versus tool operation

TRADIX provides discovery and engineering continuity, not mandatory runtime mediation.

- Finding a tool: use the TRADIX catalogue and documentation.
- Building or upgrading a tool: use TRADIX's factory lifecycle.
- Running a completed tool: run that tool directly in its own supported environment.
- Exporting or moving a tool: use that tool's documented export and migration procedures.
- Retiring a tool: follow its own data-retention and removal rules.

A tool must not call TRADIX merely to authorize its normal operation unless that dependency is separately approved as an explicit product requirement.

## 7. Change control

This map records the owner's clarified architecture as a proposed reference in this review branch. The Foundational Architecture Charter remains the governing source for builder-versus-owner boundaries. This map specializes that rule for the factory/toolbox relationship.

- Tool-specific specifications may add operational detail but may not make TRADIX a mandatory runtime dependency by implication.
- If an existing document or implementation describes TRADIX as merely one optional contributor among peer tool builders, that description is superseded by this model: TRADIX is the factory responsible for building all portfolio tools.
- Changes to identity, ownership, data boundaries, or mandatory runtime dependencies require explicit owner approval and a versioned amendment.
- Do not claim that a proposed tool is implemented or operational until its acceptance evidence exists.

## 8. One-line reminder

**TRADIX is the permanent factory and toolbox. It builds every tool and keeps developing itself. Every completed tool has its own identity and operates independently, without needing the toolbox beside it.**
