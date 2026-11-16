# TRADIX — Project Status

**Snapshot:** 2026-11-16  
**Repository:** `grinlife4-stack/TRADIX`  
**Active PR:** [#3 — Define TRADIX executive runtime architecture](https://github.com/grinlife4-stack/TRADIX/pull/3)  
**Working branch:** `factory/executive-runtime-architecture-v0-1`  
**Production policy:** Neon Production and `main` remain untouched unless explicitly approved.

## 1. Executive status

TRADIX has a verified deterministic demonstration path and a tested, runnable, read-only memory gateway. It is **not an autonomous software factory**.

The current proof covers Python tests, disposable PostgreSQL 17 schema/integrity tests, and Node HTTP integration tests in GitHub Actions. It does not prove a deployed runtime, live model execution, persistent orchestration, autonomous implementation, or unattended recovery.

## 2. Source control and CI

PR #3 is **open, Draft, and unmerged**. Its latest verified head at this snapshot is:

`998b8f2f0b5bf99c6c3c8db78ea6fb288899dd5d`

Successful workflow runs on that exact head:
- [Python tests — 43813039419](https://github.com/grinlife4-stack/TRADIX/actions/runs/43813039419)
- [Factory ledger + memory gateway SQL/HTTP integration — 43813039302](https://github.com/grinlife4-stack/TRADIX/actions/runs/43813039302)

The integration workflow applies the draft schemas only to disposable PostgreSQL 17, runs SQL integrity checks, starts the Node gateway, and exercises health, authorization, missing-project, invalid-key, and authenticated context retrieval paths.

PR #2 remains open/Draft according to the last recorded repository audit; re-check live metadata before making release decisions. PR #1 is historical and merged.

## 3. Database responsibility boundary

The previous status text described multiple schemas inconsistently. The intended responsibility boundary is now explicit:

- **Operational factory ledger (`factory.*`)**: authoritative record for projects, tasks, attempts, task events, approvals, artifacts, and evidence. It owns execution state and audit history.
- **Memory/context gateway (`memory_*`)**: read-only context retrieval for an authorized project. It is not an execution ledger, does not own task state, and must not become a second authority for task lifecycle.
- **Object storage (B2)**: binary artifact payloads only; metadata, ownership, hashes, and lifecycle references belong in the operational ledger.

This is an architecture decision for implementation and review, **not approval to migrate either schema**. Existing Neon prototypes are historical experiments and are not canonical. Before any Neon trial, reconcile table names, ownership, foreign keys, retention, and migration strategy against this boundary. No production migration is authorized.

## 4. Neon state and safety boundary

Last read-only inspection recorded:
- Neon project: `TRADIX NEON`, project ID `royal-art-56263739`, region `aws-us-east-2`, PostgreSQL 18.
- `production`: ready, zero application tables.
- `factory-ledger-prototype-2026-11-15`: isolated prototype.
- `mcp-migration-2026-11-15T12-10-55`: isolated prototype.

These branch/table counts are the last recorded inspection, not a fresh live database read in this commit. No migration from this PR has been applied to Neon. Keep Production untouched.

## 5. Implemented and verified

- Task-envelope validation and evidence-gated state-transition contracts.
- Provider-neutral model request/response interface; tests use a fake provider, not a live model.
- Deterministic fixture demo that uses a reviewed template, runs tests/static checks, and emits a candidate artifact.
- Draft operational factory ledger with disposable PostgreSQL integrity tests.
- B2 private-bucket connectivity, list, upload, and read-back test from an ephemeral GitHub runner.
- Read-only Node memory gateway with HTTP entrypoint, `npm start`, runtime README, SQL tests, and HTTP integration tests.
- JSON schemas for project state, decisions, evidence, and checkpoints.

## 6. Not yet operational

- Live model provider, credential management, and verified spend limits.
- Persistent task orchestrator and workers that claim and execute real tasks.
- Canonical schema migrations applied to an isolated Neon branch and used by runtime.
- Runtime deployment and health monitoring.
- Persistent artifact lifecycle integrated with ledger metadata, plus backup/restore proof.
- Leases, heartbeats, retries, checkpoints, takeover, and stale-worker fencing.
- Independent semantic review by a live model.
- Repeated end-to-end fault-injection and recovery runs.
- Unattended autonomous operation.

## 7. Risks and gates

1. **Schema implementation gap:** the responsibility boundary is defined above, but the draft migrations still need a reviewed reconciliation and canonical migration plan.
2. **No persistent executor:** CI proves bounded tests, not a continuously running factory.
3. **No live model path:** the provider interface is not a connected provider.
4. **Artifact recovery unproven:** B2 connectivity is not backup/restore verification.
5. **Governance:** observed branches were not protected in the last audit. Draft PRs and human approval remain necessary; do not assume branch protection enforces this boundary.

## 8. Next execution sequence

1. Review the schema boundary and produce one canonical migration plan; do not apply it to Production.
2. Add migration compatibility and negative tests against disposable PostgreSQL.
3. Build a minimal persistent orchestrator on an isolated environment, with idempotent task claims, attempt records, bounded retries, and explicit approval gates.
4. Add a model-provider adapter with secrets kept outside the repository and hard spend/time limits.
5. Integrate B2 artifact payloads with ledger metadata and prove backup/restore.
6. Deploy only to an isolated test environment; run fault-injection, recovery, and security tests.
7. Consider release/merge only after review and verified CI. Production remains a separate explicit approval gate.

## 9. Update protocol

Every substantive work session must update this file with the exact branch/head SHA, PR state, CI run IDs, database changes, external side effects, completed tests, unverified claims, blockers, and next action.

A component is **operational** only when its real execution path has run and its result has been independently verified. A design, adapter, migration file, or passing isolated test alone is not proof of production operation.
