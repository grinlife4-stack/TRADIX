# EXVARLI — local project instructions

First read the repository-root `AGENTS.md` and the [Ecosystem Master Map](../../docs/ECOSYSTEM_MASTER_MAP.md). Then read this project's own README, dossier, decision log, and status before making changes.

- **Target:** EXVARLI
- **Classification:** independent project and specialist financial-management capability
- **Boundary:** EXVARLI provides reusable financial-management capabilities to independent projects. It is not a parent or owner of those projects. Preserve a separate ledger, accounts, funds, permissions, audit trail, and export boundary for every served project.

EXVARLI may contribute reusable financial tools, workflows, controls, or options to the shared toolbox. Projects may use these capabilities when needed, but each project retains its own financial records, account ownership, funds, permissions, and decisions. A shared financial tool must never merge the books or balances of the projects it serves.

Keep EXVARLI's own source, data, financial records, accounts, and credentials separate from the records and secrets of the projects it serves. Reusable contributions must not expose project-specific financial data or credentials.

## Mandatory ready-made capability audit — EXVARLI

Before designing or developing any new financial capability, or making a material architectural change to a financial workflow, perform and record an audit of ready-made tools, services, libraries, and existing toolbox capabilities relevant to:

- financial management and general ledger;
- transaction reconciliation;
- bank connectivity and retrieval of banking information;
- financial reporting;
- audit, controls, and traceability.

The audit is not merely a search for products with similar names. For the specific requirement, determine whether an existing option can deliver the required capability without rebuilding it, with lower total cost and risk.

Record, at minimum:
1. Suitable existing options, including relevant shared-toolbox capabilities.
2. Whether each can be used directly, integrated through a defined interface, or adapted.
3. Total cost, licensing, security, operational and maintenance risks.
4. Data ownership, portability/export, replaceability, and vendor lock-in implications.
5. The reason for choosing reuse/integration or custom development.

If custom development is selected, record why the ready-made options are unsuitable or materially worse. This gate applies to new financial capabilities and material architectural changes, not routine bug fixes or minor maintenance that does not introduce a new capability. Do not adopt a ready-made tool merely because it exists.

If work crosses into another project or shared tool, identify both sides, the interface, data owner, permissions, maintenance responsibility, and acceptance authority before editing. If unclear, stop and report the ambiguity.
