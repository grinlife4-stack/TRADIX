# Mandatory project-entry instructions

Before doing any work in this repository, read these documents in order:

1. [Ecosystem Master Map](docs/ECOSYSTEM_MASTER_MAP.md) — project independence, shared evolving toolbox, optional reuse, and data boundaries.
2. [Foundational Architecture Charter](docs/FOUNDATIONAL_ARCHITECTURE_CHARTER.md) — TRADIX production and ownership boundaries.
3. The README, dossier, decision log, and current status for the exact project or tool being changed.

## Non-negotiable mental model

- MegaMarket, NEXORA, info_engine, and other products/projects are independent.
- The ecosystem has a shared toolbox that grows gradually from actual project needs.
- Each project decides its own needs. It may build a tool, improve an existing tool, or contribute one or more reusable capabilities/options to the toolbox.
- Other projects may use a toolbox capability when it fits; use is optional, never imposed.
- TRADIX provides production capabilities such as design, build, test, security, packaging, and release preparation. It is not the entire toolbox and does not own the projects it helps.
- EXVARLI provides specialist financial-management capabilities. It is not above or owner of the projects it serves.
- Tools and capabilities remain independently maintainable, replaceable, and reusable.
- Project-specific data, finances, accounts, credentials, users, and decisions stay isolated and owned by that project.
- Repository/folder placement does not establish ownership or hierarchy.
- A shared tool or toolbox contribution does not authorize project merger, transfer of ownership, or automatic data/code sharing.

## Mandatory ready-made capability audit — TRADIX

Before designing or developing any new capability, or making a material architectural change, perform and record an audit of ready-made tools, services, libraries, and existing toolbox capabilities across the full software production lifecycle:

- design and development;
- testing and quality assurance;
- security;
- deployment and infrastructure;
- monitoring and maintenance;
- documentation.

The audit is not merely a search for products with similar names. For the specific requirement, determine whether an existing option can deliver the required capability without rebuilding it, with lower total cost and risk.

Record, at minimum:
1. Suitable existing options, including relevant shared-toolbox capabilities.
2. Whether each can be used directly, integrated through a defined interface, or adapted.
3. Total cost, licensing, security, operational and maintenance risks.
4. Data ownership, portability/export, replaceability, and vendor lock-in implications.
5. The reason for choosing reuse/integration or custom development.

If custom development is selected, record why the ready-made options are unsuitable or materially worse. This gate applies to new capabilities and material architectural changes, not routine bug fixes or minor maintenance that does not introduce a new capability. Do not adopt a ready-made tool merely because it exists.

## Required pre-edit checklist

Before editing:
1. State internally and in the work plan which exact project/tool is the target.
2. Verify the current repository, branch, and paths.
3. Read the target's own instructions and current project records.
4. Identify any cross-project interface, data, permission, maintenance, or operational effect.
5. If scope or ownership is ambiguous, stop and ask for clarification rather than guessing.

Never:
- merge independent project data or ledgers for convenience;
- force a project to adopt a shared tool;
- make a project permanently dependent on a shared tool without explicit approval;
- let a shared tool retain project secrets or private data after its authorized need ends;
- expose project-specific implementation or data merely to make a capability reusable;
- edit neighboring projects because they share a repository;
- infer hierarchy from folder names or repository layout.

For Claude Code, also read the applicable `CLAUDE.md`. For other agents, follow their repository-instruction conventions. If the agent does not load these files automatically, retrieve them explicitly before work.
