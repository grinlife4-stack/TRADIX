# TRADIX — Project Status

**Snapshot:** 2026-11-16  
**Repository:** `grinlife4-stack/TRADIX`  
**Active PR:** [#3 — Define TRADIX executive runtime architecture](https://github.com/grinlife4-stack/TRADIX/pull/3)  
**Working branch:** `factory/executive-runtime-architecture-v0-1`  
**Last verified code/test baseline:** `bfc225bc6a5f9f50195706c4858b7ddffc227a8f`  
**Production policy:** Neon Production and `main` remain untouched unless explicitly approved.

## 1. Executive status

TRADIX has a verified deterministic demonstration path, a tested runnable read-only memory gateway, draft factory-ledger SQL, and provider-neutral model/task contracts. It is **not yet an autonomous software factory**.

Verified branch head `bfc225bc6a5f9f50195706c4858b7ddffc227a8f` passed both Python tests and disposable PostgreSQL 17 plus Node HTTP integration. The ledger migration now runs in CI as a non-superuser `CREATEROLE` identity, not as PostgreSQL superuser. These checks do not prove a deployed runtime, live model execution, persistent orchestration, autonomous implementation, or unattended recovery.

## 2. Source control and CI

PR #3 is **open, Draft, and unmerged**. Last code/test-verified branch head:

`bfc225bc6a5f9f50195706c4858b7ddffc227a8f`

Successful workflow runs on that exact head:
- [Python tests — 43817870900](https://github.com/grinlife4-stack/TRADIX/actions/runs/43817870900): success.
- [Factory ledger + memory gateway SQL/HTTP integration — 43817871156](https://github.com/grinlife4-stack/TRADIX/actions/runs/43817871156): success. The ledger migration and full role-boundary tests ran as a non-superuser `CREATEROLE` identity.

A subsequent documentation-only status commit `e31365a13b9083150648c77989743c9338c9381a` also passed both workflows: [Python tests — 43817413028](https://github.com/grinlife4-stack/TRADIX/actions/runs/43817413028) and [Factory ledger integration — 43817413000](https://github.com/grinlife4-stack/TRADIX/actions/runs/43817413000).

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
- Draft least-privilege database roles: `factory_runtime` is NOLOGIN and read-only on tables, with EXECUTE only on the transition function; `factory_executor_owner` is NOLOGIN, non-superuser, not a table owner, and holds only the privileges required by the SECURITY DEFINER function.
- Fixed search_path on the SECURITY DEFINER function, revoked PUBLIC execution, and prohibited application callers from claiming `actor_type='human'`.
- Disposable PostgreSQL tests prove allowed function-mediated transitions and deny direct projection writes, direct event inserts, immutable-row updates, TRUNCATE, runtime-to-owner role membership, and human-actor spoofing.
- B2 private-bucket connectivity, list, upload, and read-back test from an ephemeral GitHub runner.
- Read-only Node memory gateway with HTTP entrypoint, `npm start`, runtime README, SQL tests, and HTTP integration tests.
- JSON schemas for project state, decisions, evidence, and checkpoints.
- Latest CI on head `bfc225bc6a5f9f50195706c4858b7ddffc227a8f`: both workflows successful (Python `43817870900`; SQL/HTTP `43817871156`).

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

1. **Schema enforcement gap:** a draft `factory_runtime` NOLOGIN role, restricted grants, SECURITY DEFINER transition path, and privilege-boundary tests are CI-verified on PostgreSQL 17 using a non-superuser migration identity without CREATEROLE. They have not been applied to Neon. Atomic worker claiming, lease ownership, and fencing are also not implemented.
2. **No persistent executor:** CI proves bounded tests, not a continuously running factory.
3. **No live model path:** the provider interface is not a connected provider.
4. **Artifact recovery unproven:** B2 connectivity is not backup/restore verification.
5. **Governance:** observed branches were not protected in the last audit. Draft PRs and human approval remain necessary; do not assume branch protection enforces this boundary.
6. **Stacked PRs:** PR #3 depends on PR #2's branch. Release ordering and eventual consolidation need explicit review.

## 8. Next execution sequence

1. Role provisioning is now verified against PostgreSQL 17 using a non-superuser `CREATEROLE` migration identity. Neon-specific migration remains unexecuted; do not apply it without separate approval.
2. Before any isolated Neon-branch trial, verify the exact connection role and inspect resulting role membership, function owner, ACLs, and default privileges.
3. Implement atomic worker claims, attempt ownership, bounded retries, lease expiry, heartbeat, fencing, and stale-worker rejection, with concurrency/fault-injection tests.
4. Add one model-provider adapter only after privacy, credentials, rate limits, and a hard spend ceiling are verified.
5. Integrate B2 artifact payloads with ledger metadata and prove backup/restore.
6. Deploy only to an isolated test environment; run security, restart, concurrency, and recovery tests.
7. Consider release/merge only after review and verified CI. Production remains a separate explicit approval gate.

## 9. Immediate execution update (2026-11-16)

- Added `SECURITY DEFINER` with fixed search path to `factory.transition_task(...)` and transferred ownership to a dedicated NOLOGIN/non-superuser function-owner role with only required table privileges.
- Added draft `factory_runtime` NOLOGIN role: SELECT-only table access plus EXECUTE on the controlled transition function; direct writes and sequence access are revoked.
- Added SQL integration assertions for allowed controlled transition and denied direct projection/event/immutable-row/TRUNCATE writes, plus actor spoofing and role-isolation checks.
- Added runtime privilege-boundary documentation.
- Verified head `2523cc33350eb60a196f79b1853b57739dc1a757`: Python tests run `43817318325` and factory ledger + memory gateway SQL/HTTP integration run `43817318307`, both successful.
- An earlier integration run exposed a test-output parsing issue; it was corrected, and the complete privilege suite passed on the verified head.
- No Neon database, Production, `main`, secrets, deployment, or merge was touched.

## 10. Update protocol

Every substantive work session must update this file with the exact branch/head SHA, PR state, CI run IDs, database changes, external side effects, completed tests, unverified claims, blockers, and next action.

A component is **operational** only when its real execution path has run and its result has been independently verified. A design, adapter, migration file, or passing isolated test alone is not proof of production operation.


## 11. Neon role-provisioning compatibility review (2026-11-16)

**Decision:** A separate Neon API role-provisioning operation is not required, but role provisioning should be a one-time bootstrap separate from ordinary schema migrations. The current project exposes `neondb_owner` with `CREATEROLE`, `CREATEDB`, `LOGIN`, and `NOSUPERUSER`. Neon supports SQL-based role management; the two factory roles are `NOLOGIN`, so they do not need passwords. Run the bootstrap with a trusted administrator; the schema migration identity then needs database `CREATE` and SET-only membership in `factory_executor_owner`, not `CREATEROLE`.

Read-only inspection of the existing branch `factory-ledger-prototype-2026-11-15` confirmed PostgreSQL 18.7 and the role attributes above. That branch currently has no `factory` schema and neither factory role exists. No schema or role was created during this inspection. The `production` branch was not queried for writes and was not modified.

Two PostgreSQL 16+ migration issues were found and corrected:

1. A non-superuser with `CREATEROLE` receives automatic creator membership with `ADMIN TRUE`, but `SET FALSE` and `INHERIT FALSE`. A separate bootstrap now creates the NOLOGIN factory roles and explicitly grants `factory_executor_owner` to the selected migration identity with `SET TRUE, INHERIT FALSE`. Runtime is not granted membership in the owner role.
2. Function ACL revocation/grant must happen while the migration identity still owns the function. The ACL operations now occur before `ALTER FUNCTION ... OWNER TO factory_executor_owner`; otherwise a non-superuser migration identity loses authority to change the function ACL after ownership transfer.

CI provisions `tradix_migrator` without `CREATEROLE`, grants it only database `CREATE` plus SET-only membership in the function-owner role, provisions the factory roles separately as administrator, and applies the draft migration as `tradix_migrator`. Assertions verify the owner-role SET/INHERIT boundary and runtime isolation. Exact successful runs on branch head `bfc225bc6a5f9f50195706c4858b7ddffc227a8f`:
- Python: [43817870900](https://github.com/grinlife4-stack/TRADIX/actions/runs/43817870900)
- SQL + memory gateway integration: [43817871156](https://github.com/grinlife4-stack/TRADIX/actions/runs/43817871156)

**Remaining boundary:** disposable PostgreSQL 17 CI plus read-only inspection of Neon PostgreSQL 18 is not a live Neon migration test. Before any future isolated Neon-branch trial, verify the actual connection identity and inspect role memberships, function ownership, ACLs, and default privileges after application. Production, `main`, secrets, deployments, and merges remain untouched.
