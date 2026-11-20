# Portfolio Storage Monitor

Optional, read-only, removable utility for measuring storage independently across registered portfolio projects and aggregating the resulting reports.

**Current status: DESIGN DOSSIER ONLY.** No scanner, scheduler, notification integration, or live inventory runner is implemented yet.

## Rules

- Read [the governing specification](../../docs/PORTFOLIO_STORAGE_MONITOR.md) before implementation.
- Default mode is MANUAL. No background work is permitted unless SCHEDULED mode is explicitly enabled.
- Keep project/source boundaries independent; aggregate normalized measurement records only.
- Never interpret failed or inaccessible sources as zero.
- Do not make TRADIX core, Gateway, EventStore, or any product depend on this tool.
- Keep this directory removable without changing product behavior.
- Do not add provider credentials, private project data, or secrets to this directory or repository.

## Planned structure

The implementation may introduce these components as needed:

- `registry/`: project/source references and measurement policies (no secrets)
- `scanners/`: read-only provider-specific inventory adapters
- `schemas/`: normalized measurement records
- `aggregator/`: portfolio summary and coverage validation
- `reports/`: exportable JSON/CSV/Markdown outputs
- `config/`: optional schedule and alert thresholds

Do not create empty placeholder modules or claim functionality before implementation and tests exist.

## First implementation milestone

Build a local/manual read-only inventory runner and test it against isolated sample fixtures. Add real provider adapters only after their access, cost, and regional eligibility are verified. Scheduling and notifications are separate later milestones.
