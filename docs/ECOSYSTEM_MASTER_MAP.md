# Ecosystem Master Map — Independent Projects and Reusable Equipment

**Document ID:** ECOSYSTEM-MAP-001  
**Status:** Governing portfolio rule  
**Approved by:** Project owner, 2026-11-19  
**Canonical location:** `grinlife4-stack/TRADIX/docs/ECOSYSTEM_MASTER_MAP.md`

## 1. The simplest correct mental model

The ecosystem contains **independent construction projects** and **reusable equipment**.

- MegaMarket, NEXORA, and every other separately defined product/project are their own construction sites.
- TRADIX, EXVARLI, and other shared capabilities are equipment used to help those projects get built, tested, secured, operated, or financially managed.
- Equipment is not the building. A project does not become a department, child, or extension of the equipment that serves it.
- When a job is complete, the equipment is detached/released and can be used on the next project.
- The equipment may be important or even essential during a particular phase. That does not create permanent ownership, hierarchy, or lock-in.

**Short rule: Independent projects. Reusable equipment. Temporary service relationship. Clean separation after use.**

## 2. The current analogy

| Real-world analogy | Ecosystem meaning | Boundary |
|---|---|---|
| A construction site/building project | MegaMarket, NEXORA, and other independent projects | Own purpose, decisions, data, records, assets, finances, users, and lifecycle |
| A large specialist crane / production factory | TRADIX | Reusable design, build, test, security, packaging, and release-preparation capability; not the whole shared-equipment ecosystem |
| A smaller specialist crane for financial work | EXVARLI | Reusable financial-management capability for multiple projects; not above, owner of, or merged with the projects it serves |
| Drills, lifting tools, scaffolding, testing instruments, etc. | Other reusable capabilities | Each has a defined function and interface; none should be duplicated without reason |
| The equipment pool | The ecosystem's collective shared-capability layer | The combined set of reusable tools/services, not one single project |

TRADIX and EXVARLI are examples of reusable equipment with different functions and capacities. Neither one alone is the entire shared-capability layer.

## 3. Independent project boundary

Every project remains a separate building site, whether its files are stored in a separate repository or in a directory inside another repository.

Each project retains control of its own:
- identity, mission, roadmap, priorities, and acceptance decisions;
- source records, business data, files, content, and intellectual property;
- accounts, credentials, permissions, and customer relationships;
- income, expenses, budgets, liabilities, wallets, and financial records;
- operational decisions, release approvals, and lifecycle.

A shared repository path, common developer, common tool, common account used for administration, or service relationship does **not** make one project a child or department of another. Repository layout is not an ownership chart.

## 4. Equipment use lifecycle

The normal lifecycle is:

1. **Project defines the need.** The project requests a specific capability and defines acceptance criteria.
2. **Equipment is assigned temporarily.** The equipment receives only the access and inputs necessary for that task.
3. **Work is performed through a defined interface.** The project remains the decision-maker for its own domain.
4. **The result is accepted by the project.** Acceptance does not transfer ownership of the project or its data to the equipment provider.
5. **Equipment is detached/released.** Access tokens, permissions, temporary copies, and project-specific access are revoked or cleared as appropriate.
6. **Equipment is available for reuse.** Generic tools, code, reusable methods, and equipment-owned operational knowledge may remain; project-specific data and secrets do not become shared.

A project may continue using equipment for a later task, but that is a new or continuing explicitly scoped service relationship, not permanent ownership.

## 5. Non-negotiable separation rules

- Never merge project data, financial records, accounts, wallets, credentials, or customer records merely because projects use the same equipment.
- EXVARLI may provide financial-management services and portfolio-level views, but each project's ledger, account ownership, funds, permissions, and audit trail remain distinct.
- TRADIX may design, build, test, secure, package, and prepare products, but building a project does not make TRADIX its owner or default operator.
- Shared capabilities must be replaceable. A project must be able to stop using, replace, or export away from a piece of equipment without losing its identity, data, assets, or continuity.
- Shared equipment must not silently become a mandatory runtime dependency.
- Reuse common capabilities where they fit; do not force a capability onto a project where it does not fit.
- Keep project-specific state isolated even when the same tool serves several projects.
- Do not infer project hierarchy from names, repository paths, folders, deployment accounts, or the order in which projects were created.

## 6. How to classify a new item

Before treating anything as a project or shared tool, establish its role from an approved project dossier or an explicit owner decision.

Ask:
- Does it have its own mission, roadmap, data, assets, decisions, and lifecycle? It is an independent project.
- Does it provide a reusable capability to multiple independent projects? It is shared equipment/service.
- Does it do both? Record both roles explicitly and keep its own project boundary separate from the service boundary it provides.

Do not invent a parent-child relationship to make a diagram look tidy.

## 7. AI and developer entry protocol

Before any AI-assisted or human engineering work in any project/repository:

1. Read this master map first.
2. Read the repository's root `AGENTS.md` and the applicable `CLAUDE.md` or tool-specific instructions.
3. Identify the exact target project and whether the current task concerns a project or reusable equipment.
4. Read that target's own README, dossier, decision log, and current status.
5. Confirm repository, branch, and target paths before editing.
6. Keep changes inside the selected scope. Do not edit another project or shared equipment merely because it is nearby.
7. If the requested change crosses project boundaries, define the interface, data ownership, permissions, and acceptance responsibilities before implementation.
8. If documents conflict or the role is unclear, stop and report the conflict. Do not silently choose an interpretation.

### Important limitation

`AGENTS.md`, `CLAUDE.md`, and editor-specific instruction files are agent conventions, not a universal GitHub-enforced mechanism. Compatible coding agents can load them automatically. When using an interface that does not automatically load repository instructions, the operator/assistant must explicitly retrieve this master map before work. A file existing in GitHub alone does not guarantee every AI product has read it.

## 8. Change control

This map records the project owner's governing mental model. Project-specific dossiers may add details but must not reverse these boundaries. Any change to the model requires explicit owner approval and a dated, versioned amendment.

If implementation or an older document conflicts with this map, record the discrepancy and propose a controlled correction. Do not pretend the conflict does not exist.

## 9. One-line reminder

**MegaMarket and NEXORA are separate buildings. TRADIX, EXVARLI, and other shared capabilities are reusable equipment. They serve projects, detach when their work is done, and move on to the next project.**
