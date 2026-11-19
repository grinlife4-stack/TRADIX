# Ecosystem Master Map — Independent Projects and Reusable Equipment

**Document ID:** ECOSYSTEM-MAP-001  
**Status:** Proposed governing portfolio rule; pending owner review  
**Canonical location:** `grinlife4-stack/TRADIX/docs/ECOSYSTEM_MASTER_MAP.md`

## 1. The simplest correct mental model

The ecosystem contains **independent projects** and a **shared, evolving toolbox**.

- MegaMarket, NEXORA, info_engine, and every other separately defined product/project are independent projects with their own purpose and lifecycle.
- TRADIX, EXVARLI, and other tools/capabilities are independently maintainable equipment or specialist projects that can contribute capabilities to the shared toolbox and/or serve individual projects.
- The toolbox is not a parent organization, product owner, command center, or mandatory platform. It is a growing collection of reusable tools and capabilities.
- Projects develop according to their own needs. A project may create a new tool, improve an existing tool, or contribute one or more reusable options/capabilities to the toolbox.
- Other projects may use a capability when it fits their needs. Availability never means compulsory adoption.

**Short rule: Independent projects. One evolving shared toolbox. Project-led contributions. Optional reuse. No forced integration.**

## 2. The mechanic's toolbox model

Think of a mechanic's toolbox. It contains many tools: wrenches, pliers, drills, measuring instruments, and specialist equipment. The mechanic does not use every tool on every job. A tool is present because it may be useful when a particular need arises.

The ecosystem works the same way:

- The shared toolbox grows gradually as real project needs arise.
- Each project identifies its own needs and decides what to build or improve.
- A project may contribute one or several tools, modules, adapters, workflows, or capabilities to the toolbox.
- A contribution should be made reusable where practical, without forcing the contributing project to expose its private implementation, data, or business logic.
- A project may use any existing tool that fits, ignore tools it does not need, or use a different solution.
- The toolbox is not expected to be complete at the beginning. It becomes more capable through actual use and project contributions.

TRADIX and EXVARLI are examples of separately maintainable capabilities/equipment with different functions. Neither is the whole toolbox, and neither automatically governs the projects or tools around it.

## 3. Independent project boundary

Every project remains a separate project, whether its files are stored in a separate repository or in a directory inside another repository.

Each project retains control of its own:
- identity, mission, roadmap, priorities, and acceptance decisions;
- source records, business data, files, content, and intellectual property;
- accounts, credentials, permissions, and customer relationships;
- income, expenses, budgets, liabilities, wallets, and financial records;
- operational decisions, release approvals, and lifecycle.

A shared repository path, common developer, common tool, common account used for administration, or service relationship does **not** make one project a child or department of another. Repository layout is not an ownership chart.

## 4. Contribution and reuse lifecycle

The shared toolbox grows through real work, not through a speculative central design exercise.

1. **A project identifies a need.** The project defines the problem, scope, and acceptance criteria.
2. **Choose the least wasteful solution.** Check whether an existing toolbox capability fits. If not, the project may build a project-local solution, extend an existing tool, or create a new tool.
3. **Separate reusable capability from project-specific material.** Where practical, isolate the generic function, interface, and configuration from the project's private data, secrets, business rules, and identity.
4. **Contribute when useful.** A project may add the reusable capability or option to the shared toolbox. This is not automatic: suitability, security, documentation, ownership, maintenance, and dependencies must be clear.
5. **Reuse remains optional.** Other projects may adopt the capability if it meets their needs. They are not required to do so and do not inherit the contributing project's roadmap or dependencies.
6. **Maintain and replace independently.** Each tool has a clear maintainer, version/interface, dependencies, and removal or replacement path. A project must not lose its own continuity if a shared tool changes or disappears.

The toolbox is allowed to grow organically. Do not create tools merely to fill a catalog, and do not impose a shared solution where a project's own simpler solution is better.

## 5. Equipment use and service lifecycle

When a project uses a tool or specialist service:

1. The project defines the task and acceptance criteria.
2. The tool receives only the access and inputs necessary for that task.
3. Work is performed through a defined interface where practical.
4. The project accepts or rejects the result.
5. Temporary access, credentials, and copies are revoked or cleared when no longer needed.
6. The tool remains independently maintainable and may be used by another project.

A project may continue using a tool for later work, but this does not create ownership, hierarchy, or permanent lock-in.

## 6. Non-negotiable separation rules

- Never merge project data, financial records, accounts, wallets, credentials, or customer records merely because projects use the same tool.
- EXVARLI may provide financial-management capabilities and portfolio-level views, but each project's ledger, account ownership, funds, permissions, and audit trail remain distinct.
- TRADIX may provide production capabilities such as design, build, test, security, packaging, and release preparation, but this does not make TRADIX the owner or default operator of a product.
- Shared tools must be replaceable. A project must be able to stop using, replace, or export away from a tool without losing its identity, data, assets, or continuity.
- Shared tools are not mandatory runtime dependencies unless the project owner explicitly approves that dependency.
- Reuse common capabilities where they fit; do not force a capability onto a project where it does not fit.
- Keep project-specific state isolated even when the same tool serves several projects.
- A contribution to the toolbox does not transfer ownership of the contributing project, its private data, or its entire source code.
- Do not infer project hierarchy from names, repository paths, folders, deployment accounts, or the order in which projects were created.
- No project merger, transfer of ownership, or cross-project data integration is authorized by the existence of the toolbox.

## 7. How to classify a new item

Before treating anything as a project or shared tool, establish its role from an approved project dossier or an explicit owner decision.

Ask:
- Does it have its own mission, roadmap, data, assets, decisions, and lifecycle? It is an independent project.
- Does it provide a reusable capability to other projects? It may also be a tool/equipment contributor.
- Does it do both? Record the project identity and the reusable capability as separate concerns. Its role as a tool does not erase its independent project boundary.

Do not invent a parent-child relationship to make a diagram look tidy.

## 8. AI and developer entry protocol

Before any AI-assisted or human engineering work in any project/repository:

1. Read this master map first when it is available and applicable.
2. Read the repository's root `AGENTS.md` and the applicable `CLAUDE.md` or tool-specific instructions.
3. Identify the exact target project and whether the current task concerns a project, a tool, or a contribution to the shared toolbox.
4. Read that target's own README, dossier, decision log, and current status.
5. Confirm repository, branch, and target paths before editing.
6. Keep changes inside the selected scope. Do not edit another project or shared tool merely because it is nearby.
7. If a change crosses project boundaries, define the interface, data ownership, permissions, maintenance responsibility, and acceptance responsibilities before implementation.
8. If documents conflict or the role is unclear, stop and report the conflict. Do not silently choose an interpretation.

### Important limitation

`AGENTS.md`, `CLAUDE.md`, and editor-specific instruction files are agent conventions, not a universal GitHub-enforced mechanism. Compatible coding agents can load them automatically. When using an interface that does not automatically load repository instructions, the operator/assistant must explicitly retrieve the applicable instructions. A file existing in GitHub alone does not guarantee every AI product has read it.

## 9. Change control

This map records the project owner's stated architecture as a proposed reference in this review branch. Project-specific dossiers may add details but must not reverse the independence, optional reuse, and data-separation boundaries. Any change to those boundaries requires explicit owner approval and a dated, versioned amendment.

If implementation or an older document conflicts with this map, record the discrepancy and propose a controlled correction. Do not pretend the conflict does not exist.

## 10. One-line reminder

**Projects remain independent. Their real needs gradually build a shared toolbox. Any project may contribute reusable tools or capabilities, and any other project may use them when useful, without forced adoption, merger, or transfer of identity and data.**
