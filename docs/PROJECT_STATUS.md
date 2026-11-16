# TRADIX — Project Status

**Snapshot:** 2026-11-16  
**Repository:** `grinlife4-stack/TRADIX`  
**Active PR:** [#3 — Define TRADIX executive runtime architecture](https://github.com/grinlife4-stack/TRADIX/pull/3)  
**Working branch:** `factory/executive-runtime-architecture-v0-1`  
**Verified head:** `3c5d5236046f03ace7a04224fa53064e58c9f471`  
**Production policy:** Neon Production and `main` remain untouched unless explicitly approved.

## 1. Executive status

TRADIX has a verified deterministic demonstration path, a tested runnable read-only memory gateway, draft factory-ledger SQL, and provider-neutral model/task contracts. It is **not yet an autonomous software factory**.

The latest PR head passed both Python tests and disposable PostgreSQL 17 plus Node HTTP integration. These checks do not prove a deployed runtime, live model execution, persistent orchestration, autonomous implementation, or unattended recovery.

## 2. Source control and CI

PR #3 is **open, Draft, and unmerged**. Its current head is:

`5a18742717901666bf6eb186a699949effbfaaa7`

Successful workflow runs on that exact head:
- [Python tests — 43814043279](https://github.com/grinlife4-stack/TRADIX/actions/runs/43814043279): success.
- [Factory ledger + memory gateway SQL/HTTP integration — 43814043269](https://github.com/grinlife4-stack/TRADIX/actions/runs/43814043269): success, including the new transactional task-transition tests.

The integration workflow applies draft schemas only to disposable PostgreSQL 17, runs SQL integrity checks, starts the Node gateway, and exercises health, authorization, missing-project, invalid-key, and authenticated context retrieval paths.

PR #2 is also **open, Draft, and unmerged**. It contains the earlier deterministic first-run vertical slice. PR #3 is based on PR #2's working branch, so this is a stacked-PR arrangement, not two independent releases. PR #1 is historical and merged. Do not merge either draft merely because CI is green.

## 3. Database responsibility boundary

- **Operational factory ledger (`factory.*`)**: intended authority for projects, tasks, attempts, task events, approvals, artifacts, and evidence. It owns execution state and audit history.
- **Memory/context gateway (`memory_*`)**: read-only context retrieval for an authorized project. It is not an execution ledger and does not own task lifecycle.
- **Object storage (B2)**: binary artifact payloads only; metadata, ownership, hashes, and lifecycle references belong in the operational ledger.

This is an architecture boundary for implementation and review, **not approval to migrate either schema**. Existing Neon prototypes are historical experiments and are not canonical. Before any Neon trial, reconcile table names, ownership, foreign keys, retention, grants, RLS, and migration strategy against this boundary. No Neon migration is authorized.

## 4. Neon state and safety boundary

The last recorded read-only inspection found:
- Neon project: `TRADIX NEON`, region `aws-us-east-2`, PostgreSQL 18.
- `production`: ready, zero application tables at the time of inspection.
- `factory-ledger-prototype-2026-11-15` and `mcp-migration-2026-11-15T12-10-55`: isolated prototypes.

These are historical observations, not a fresh live database read. No migration from this PR has been applied to Neon. Keep Production untouched.

## 5. Implemented and verified

- Task-envelope validation and evidence-gated in-memory state-transition contracts.
- Provider-neutral model request/response interface and strict JSON plan parser; tests use a fake provider, not a live model.
- Deterministic fixture demo that copies a reviewed template, runs tests/static checks, and emits a candidate artifact.
- Draft operational factory-ledger SQL with disposable PostgreSQL integrity tests.
- Transactional `factory.transition_task(...)` function: row-locks the task, validates allowed lifecycle edges, enforces approval/evidence gates, appends the event, updates the task projection atomically, and deduplicates exact retries while rejecting conflicting reuse of an idempotency key.
- B2 private-bucket connectivity, list, upload, and read-back test from an ephemeral GitHub runner.
- Read-only Node memory gateway with HTTP entrypoint, `npm start`, runtime README, SQL tests, and HTTP integration tests.
- JSON schemas for project state, decisions, evidence, and checkpoints.
- Latest CI on head `5a18742717901666bf6eb186a699949effbfaaa7`: both workflows successful.

## 6. Not yet operational

- Live model provider, credential management, and verified spend limits.
- Persistent task orchestrator and workers that claim and execute real tasks.
- Canonical factory schema reconciled, reviewed, and used by a runtime.
- Runtime deployment and health monitoring.
- Persistent artifact lifecycle integrated with ledger metadata, plus backup/restore proof.
- Leases, heartbeats, retries, checkpoints, takeover, and stale-worker fencing.
- Independent semantic review by a live model.
- Repeated end-to-end fault-injection and recovery runs.
- Unattended autonomous operation.

## 7. Risks and gates

1. **Schema enforcement gap:** the transactional task lifecycle function is tested, but least-privilege application roles/grants are not defined. A runtime role must not receive direct projection-write privileges that bypass the transition function. Atomic worker claiming, lease ownership, and fencing are also not implemented.
2. **No persistent executor:** CI proves bounded tests, not a continuously running factory.
3. **No live model path:** the provider interface is not a connected provider.
4. **Artifact recovery unproven:** B2 connectivity is not backup/restore verification.
5. **Governance:** observed branches were not protected in the last audit. Draft PRs and human approval remain necessary; do not assume branch protection enforces this boundary.
6. **Stacked PRs:** PR #3 depends on PR #2's branch. Release ordering and eventual consolidation need explicit review.

## 8. Next execution sequence

1. Define and test least-privilege database roles/grants so the runtime cannot bypass the transition function or mutate immutable records.
2. Finalize the canonical migration plan; do not apply it to Neon until separately reviewed and approved.
3. Implement atomic worker claims, attempt ownership, bounded retries, lease expiry, heartbeat, fencing, and stale-worker rejection, with concurrency/fault-injection tests.
4. Add one model-provider adapter only after privacy, credentials, rate limits, and a hard spend ceiling are verified.
5. Integrate B2 artifact payloads with ledger metadata and prove backup/restore.
6. Deploy only to an isolated test environment; run security, restart, concurrency, and recovery tests.
7. Consider release/merge only after review and verified CI. Production remains a separate explicit approval gate.

## 9. Update protocol

Every substantive work session must update this file with the exact branch/head SHA, PR state, CI run IDs, database changes, external side effects, completed tests, unverified claims, blockers, and next action.

A component is **operational** only when its real execution path has run and its result has been independently verified. A design, adapter, migration file, or passing isolated test alone is not proof of production operation.
