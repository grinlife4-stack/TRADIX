# Mandatory project-entry instructions

Before doing any work in this repository, read these documents in order:

1. [Ecosystem Master Map](docs/ECOSYSTEM_MASTER_MAP.md) — mandatory portfolio boundaries and reusable-equipment model.
2. [Foundational Architecture Charter](docs/FOUNDATIONAL_ARCHITECTURE_CHARTER.md) — TRADIX production and ownership boundaries.
3. The README, dossier, decision log, and current status for the exact project being changed.

## Non-negotiable mental model

- MegaMarket, NEXORA, and other products are independent construction projects.
- TRADIX is a reusable major production capability/equipment: design, build, test, security, packaging, and release preparation.
- EXVARLI is a separate reusable specialist capability/equipment for financial management. It is not above the projects it serves.
- The ecosystem's shared-equipment layer is the combined set of reusable tools and services. TRADIX is an important part, not the entirety.
- A project using equipment does not become its child, department, or property.
- Equipment may be used across projects and must be detachable/releasable after a task or project phase.
- Project-specific data, finances, accounts, credentials, users, and decisions stay isolated and owned by that project.
- Repository/folder placement does not establish ownership or hierarchy.

## Required pre-edit checklist

Before editing:
1. State internally and in the work plan which exact project/equipment is the target.
2. Verify the current repository, branch, and paths.
3. Read the target's own instructions and current project records.
4. Identify any cross-project interface, data, permission, or operational effect.
5. If scope or ownership is ambiguous, stop and ask for clarification rather than guessing.

Never:
- merge independent project data or ledgers for convenience;
- make a project permanently dependent on a shared tool without explicit approval;
- let a shared tool retain project secrets or private data after its authorized need ends;
- edit neighboring projects because they share a repository;
- infer hierarchy from folder names or repository layout.

For Claude Code, also read the applicable `CLAUDE.md`. For other agents, follow their repository-instruction conventions. If the agent does not load these files automatically, retrieve them explicitly before work.
