# TRADIX — Project Status

**Snapshot:** 2026-11-16  
**Repository:** `grinlife4-stack/TRADIX`  
**Active PR:** [#3 — Define TRADIX executive runtime architecture](https://github.com/grinlife4-stack/TRADIX/pull/3)  
**Working branch:** `factory/executive-runtime-architecture-v0-1`  
**Last verified code/test baseline:** `7019d0be800188f0054e0fbbc0cf8325912c0a0b`  
**Production policy:** Neon Production and `main` remain untouched unless explicitly approved.

## 1. Executive status

TRADIX has a verified deterministic demonstration path, a tested runnable read-only memory gateway, draft factory-ledger SQL, and provider-neutral model/task contracts. It is **not yet an autonomous software factory**.

Verified branch head `7019d0be800188f0054e0fbbc0cf8325912c0a0b` passed both Python tests and disposable PostgreSQL 17 plus Node HTTP integration. Cluster-level factory roles are provisioned separately by an administrator; the schema migration runs as a non-superuser without `CREATEROLE`. These checks do not prove a deployed runtime, live model execution, persistent orchestration, autonomous implementation, or unattended recovery.

## 2. Source control and CI

PR #3 is **open, Draft, and unmerged**. Last code/test-verified branch head:

`7019d0be800188f0054e0fbbc0cf8325912c0a0b`

Successful workflow runs on that exact head:
- [Python tests — 43818189687](https://github.com/grinlife4-stack/TRADIX/actions/runs/43818189687): success.
- [Factory ledger + memory gateway SQL/HTTP integration — 43818189686](https://github.com/grinlife4-stack/TRADIX/actions/runs/43818189686): success. Role bootstrap ran as administrator; the schema migration and privilege-boundary tests ran as a non-superuser without `CREATEROLE`.

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
- Latest CI on head `7019d0be800188f0054e0fbbc0cf8325912c0a0b`: both workflows successful (Python `43818189687`; SQL/HTTP `43818189686`).

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

CI provisions `tradix_migrator` without `CREATEROLE`, grants it only database `CREATE` plus SET-only membership in the function-owner role, provisions the factory roles separately as administrator, and applies the draft migration as `tradix_migrator`. Assertions verify the owner-role SET/INHERIT boundary and runtime isolation. Exact successful runs on branch head `7019d0be800188f0054e0fbbc0cf8325912c0a0b`:
- Python: [43818189687](https://github.com/grinlife4-stack/TRADIX/actions/runs/43818189687)
- SQL + memory gateway integration: [43818189686](https://github.com/grinlife4-stack/TRADIX/actions/runs/43818189686)

**Remaining boundary:** disposable PostgreSQL 17 CI plus read-only inspection of Neon PostgreSQL 18 is not a live Neon migration test. Before any future isolated Neon-branch trial, verify the actual connection identity and inspect role memberships, function ownership, ACLs, and default privileges after application. Production, `main`, secrets, deployments, and merges remain untouched.


## 2026-11-16 — Project identity and ledger gate hardening

PR #3 remains Draft and unmerged. The working branch now contains a draft-only ledger revision with:
- Per-project PostgreSQL login identities mapped one-to-one to a project; separate runtime and human-approval identities may exist for the same project.
- Forced row-level security across project, task, attempt, event, approval, artifact, evidence, and identity records. Policies use `session_user`, so `SET ROLE` cannot select another project's identity.
- A database trigger that rejects mapped identities unless they are restricted LOGIN roles belonging to exactly one approved authority group and not to the function-owner role.
- A separate `factory_identity_admin` role manages project-to-login mappings; it is isolated from runtime, approval authority, and function ownership.
- Human approvals restricted to the separate `factory_approval_authority` role. The actual database login is recorded in `decided_by_login`.
- Approval gates bound to a non-null attempt ID and exact equality with the task's `approval_scope`.
- Evidence gates that reject a missing attempt ID and evidence from any other attempt.

New disposable-PostgreSQL integration cases cover two-project read isolation, runtime approval forgery, trusted approver audit identity, stale approval, wrong approval scope, missing attempt, and cross-attempt evidence.

**Verification status:** code head `0e3ac18c201e9dd04533db325816d2eb08cb2fd3` passed both CI workflows: Python tests [43820898755](https://github.com/grinlife4-stack/TRADIX/actions/runs/43820898755) and PostgreSQL 17 ledger + memory-gateway SQL/HTTP integration [43820898840](https://github.com/grinlife4-stack/TRADIX/actions/runs/43820898840). The ledger migration ran as a non-superuser without `CREATEROLE`; the SQL tests passed. These are disposable PostgreSQL 17 results, not a Neon migration. No Neon SQL has been executed; no Neon branch was created; `main`, Production, secrets, deployments, and merge state remain untouched.

**Provisioning boundary:** each project runtime LOGIN and each human-approval LOGIN must be created by a trusted administrator, granted exactly one authority group, and inserted into `factory.project_identities` by a trusted provisioning identity holding SET-only membership in `factory_identity_admin`. Credentials must remain separate by project. This SQL does not itself provision or authenticate human users.


## 2026-11-16 — General-purpose factory scope and product dossier boundary

- Architecture baseline updated to version 1.2 in commit `b2f88c329f62ac906144d30a151c25c7b0223cbe`.
- TRADIX is now explicitly defined as a general-purpose production factory, not a software-only factory and not a single-product platform.
- Every product must have its own durable dossier and stable identity. The dossier governs that product's mission, requirements, decisions, tasks, evidence, resources, permissions, budget/costs, outputs, versions, and lifecycle.
- Shared factory capabilities may be reused, but product identity, data, authority, cost, execution state, and evidence must not be mixed. Cross-product transfer requires explicit authorization, provenance, and scope review.
- Software-specific tools such as Git, code Sandbox, builds, and software tests are production adapters for relevant product classes, not universal assumptions for every product.
- The trading platform is an example of an independent product made by TRADIX; it is not part of the factory's own identity or internal operating logic.
- Verification: the documentation commit was created on `factory/executive-runtime-architecture-v0-1`, under Draft PR #3. At the time of this note, the GitHub connector returned no workflow runs and an empty combined-status list for that exact commit; therefore no CI success is claimed. Recheck the exact PR head before treating this change as verified.
- No merge, Neon operation, secret change, deployment, Production action, or paid resource creation occurred.


## 2026-11-16 — Product-agnostic project registry correction

- The draft `factory.projects` table previously required every project to have a GitHub repository. That was a software-only assumption and conflicted with TRADIX's general-purpose factory scope.
- Corrected `migrations/drafts/0001_factory_ledger.sql` in commit `74aa0c5ee69209ac81d0f20cf8149f8114683565`: added required non-empty `product_type` (default `unspecified`) and made `repository_full_name` optional, while retaining validation when a repository is supplied.
- Updated `tests/test_factory_ledger_sql.sh` in commit `cecad1842402f6fc1ca104e215bdcef3701b199d` with a physical-product fixture that has no Git repository and an assertion that it registers successfully.
- Updated `docs/NEON_FACTORY_LEDGER_SCHEMA.md` in commit `75dfcb3f907bf2c3bfd20a02986a06d95fdf6a7f`.
- The architecture baseline version 1.2 was introduced in commit `b2f88c329f62ac906144d30a151c25c7b0223cbe`; it defines TRADIX as a general-purpose production factory and requires an independent dossier per product.
- Current PR #3 head at the time of this update: `75dfcb3f907bf2c3bfd20a02986a06d95fdf6a7f`. The GitHub connector returned no workflow runs and an empty combined-status list for this head. CI is therefore **unverified**, not passed or failed.
- No Neon migration, database write, Production change, merge, deployment, secret change, or paid resource creation occurred. All schema changes remain draft files in the PR branch.


## 2026-11-16 — Versioned product dossier implementation

- Added `factory.product_dossier_versions`: immutable, append-only snapshots keyed by product/project and monotonically increasing version number.
- Added controlled writer `factory.record_product_dossier(project_id, dossier, idempotency_key)`. It checks the authenticated `session_user` project mapping, validates the minimum dossier envelope and registered product type, serializes version allocation with a product-row lock, and supports exact idempotent retries.
- Runtime can read only its own dossier versions and can write only through the SECURITY DEFINER function. Direct INSERT/UPDATE/DELETE/TRUNCATE are not granted; RLS is enabled and forced; append-only triggers reject mutation.
- Added disposable-PostgreSQL integration cases for version 1/2, exact retry, cross-project write denial, product-type mismatch, required fields, cross-project read isolation, append-only enforcement, and direct-write denial.
- Migration remains draft-only. No Neon branch, Production database, secret, deployment, merge, or paid resource was touched.
- CI must be checked against the exact final PR head before this implementation is considered verified.


## 2026-11-16 — Product dossier contract and CI verification

- Added `schemas/product-dossier-v1.schema.json`, a machine-readable JSON Schema v1 contract. It defines the minimum common envelope and optional extensible sections for product-specific decisions, resources, budgets/costs, deliverables, risks, assets, dependencies, security, and domain specifications.
- Corrected the dossier writer documentation: version allocation uses a transaction-scoped advisory lock keyed by product ID.
- Exact tested commit before this schema-only follow-up: `a27216b4b9a1ccedb28f624b059e3fc033a22fcf`. On that SHA, `factory-ledger-sql` Run #114 (`43921328351`) and `tests` Run #147 (`43921328215`) both completed successfully. The SQL job applied the draft migration as a non-superuser, passed the product dossier version/idempotency, product-type, required-field, cross-project, append-only, and direct-write-denial checks, and then passed the memory gateway SQL and HTTP integration tests.
- The schema/documentation follow-up itself must receive CI on its resulting PR head before it is considered fully verified.
- No Neon or Production migration, database write, merge, deployment, secret change, or paid resource creation occurred.


## 2026-11-16 — Product dossier API verified on disposable PostgreSQL

- Added `runtime/product-dossier-api`: a Node.js HTTP service for one product per instance. It resolves product identity from the authenticated database `session_user`, rejects mixed/privileged roles and multiple identity mappings at startup, and does not accept a caller-supplied `project_id`.
- Read endpoints: product identity, latest dossier, and bounded version history. Write endpoint: append dossier through `factory.record_product_dossier` with an idempotency key. The API cannot create products, grant roles, approve work, or directly mutate dossier rows.
- Added API integration tests for bearer authentication, product resolution, write/read, exact idempotent retry, forged project identity rejection, and product-type mismatch rejection.
- Added SQL integration for a physical product with no Git repository: it receives its own dossier and cannot see TRADIX's dossier rows. TRADIX remains unable to see the physical product's dossier.
- Exact PR #3 head verified: `8d48e333898f4d5af376584dfbacb39fab526346`.
- `factory-ledger-sql` Run #125 (`43922571436`): success. Steps 1–13 completed, including disposable PostgreSQL migration, Factory Ledger SQL tests, product dossier API dependency install and HTTP integration, and memory gateway SQL/HTTP integration.
- `tests` Run #158 (`43922571415`): success; Python test suite passed.
- The API and migration remain code artifacts in Draft PR #3. No Neon migration, Production database write, deployment, merge, credential change outside disposable CI, or paid resource creation occurred.


## 2026-11-16 — Final dossier API CI confirmation

- PR #3 head `6e3b66b271c1ede9288cb5c7bb5505aafba662ae` passed both workflows:
  - `factory-ledger-sql` Run #126 (`43922797507`): success, including schema migration as a non-superuser, physical-product dossier creation, cross-product RLS isolation, JSON Schema smoke test, authenticated Product Dossier API write/read/idempotency tests, and Memory Gateway SQL/HTTP tests.
  - `tests` Run #159 (`43922797652`): success.
- No workflow failure or in-progress job remained for that SHA. Combined status endpoint returned an empty status list; the two workflow runs and their job steps are the positive CI evidence.
- This confirms disposable PostgreSQL 17 CI only. It does not prove the draft migration on Neon PostgreSQL 18 or authorize deployment.
