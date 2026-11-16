# TRADIX — Consolidated Project Status

**Snapshot date:** 2026-11-16  
**Status:** ACTIVE — first deterministic vertical slice verified; autonomous factory NOT operational  
**Repository:** `grinlife4-stack/TRADIX`  
**Default branch:** `main`  
**Status authority:** GitHub commits/PRs/Actions for source and CI; Neon branch metadata/schema for database state. This file is a dated snapshot, not a substitute for those live records.

## 1. Executive status

TRADIX has progressed beyond a skeleton repository. A bounded, deterministic factory demonstration has completed successfully, with Python tests, disposable PostgreSQL integrity tests, static review, and a traceable candidate artifact.

It is **not yet an autonomous AI software factory**. The successful demonstration used a supplied fixture task and reviewed template; it did not call a live model provider, autonomously design the implementation, persist its events/artifacts to Neon or B2, or deploy the result.

**Current maturity:** validated deterministic demo / candidate-generation path. Persistent orchestration, live model execution, canonical production ledger, runtime deployment, recovery, and unattended operation remain incomplete.

## 2. GitHub source-control state

Repository access was checked on 2026-11-16:
- Repository: `grinlife4-stack/TRADIX` (public).
- Connected identity has `admin`, `maintain`, `push`, and `pull` permissions.
- Default branch `main`: `d778e6e5c15eea353355d38c681b49a00dca1da7`.
- Observed branches:
  - `factory/phase-0-blueprint` — `f3a336bcfa164d1ace73dae04d9fbd65d0a1aa48`
  - `factory/preflight-status-2026-11-15` — `6d3652aacdf25b78bc695951f2dea5cb875026f3`
  - `factory/executive-runtime-architecture-v0-1` — `0b9108c90bb3601f0d12fd4e8e696bfacfc6cbb4`
- All four observed branches reported `protected=false`. Do not assume branch protection is enforcing the approval boundary.

### Pull requests

| PR | State | Scope | Verified result |
|---|---|---|---|
| [#1](https://github.com/grinlife4-stack/TRADIX/pull/1) | Merged | Initial factory plan and B2 adapter/workflow | Historical PR; merged |
| [#2](https://github.com/grinlife4-stack/TRADIX/pull/2) | Open, Draft | First deterministic factory execution and ledger test harness | All three associated workflows succeeded on head `6d3652a` |
| [#3](https://github.com/grinlife4-stack/TRADIX/pull/3) | Open, Draft | Executive runtime architecture, memory gateway, schemas and migration draft | Python and draft-ledger SQL workflows succeeded on head `0b9108c` |

PR #2 evidence:
- [Python tests, run 43749005069](https://github.com/grinlife4-stack/TRADIX/actions/runs/43749005069): completed successfully; PR description records **40 passed**.
- [PostgreSQL ledger tests, run 43749005080](https://github.com/grinlife4-stack/TRADIX/actions/runs/43749005080): completed successfully; PR description records **16/16 integrity checks passed**.
- [Factory first-run, run 43749005183](https://github.com/grinlife4-stack/TRADIX/actions/runs/43749005183): completed successfully. Demo task `TRADIX-DEMO-001` reached `candidate`; generated utility tests **9 passed**; deterministic static review **PASS**; evidence artifact was produced.

PR #3 evidence:
- [Python tests, run 43811245040](https://github.com/grinlife4-stack/TRADIX/actions/runs/43811245040): completed successfully.
- [Draft ledger SQL tests, run 43811245043](https://github.com/grinlife4-stack/TRADIX/actions/runs/43811245043): completed successfully.
- Important test-scope limit: `.github/workflows/factory-ledger-sql.yml` applies only `migrations/drafts/0001_factory_ledger.sql` to a disposable PostgreSQL 17 service. It does **not** execute `migrations/0001_memory_gateway.sql` and does not test the new Node.js memory gateway. Those PR #3 additions therefore remain unverified by these CI runs.

**PR description correction:** The initial PR #3 description understated its scope. It has now been updated to list the memory-gateway migration, Node.js gateway, JSON schemas, and this status record, and to state explicitly that the new migration and gateway are not yet integration-tested.

No PR #2 or PR #3 merge is recorded in this snapshot. `main` remains separate from these draft changes.

## 3. Neon database state

Neon project:
- Name: `TRADIX NEON`
- Project ID: `royal-art-56263739`
- Region: `aws-us-east-2`
- PostgreSQL version: 18

Read-only inspection on 2026-11-16 found these branches:

| Neon branch | ID | State | Application tables |
|---|---|---|---:|
| `production` (default) | `br-lingering-hall-bdh0g9if` | ready | **0** |
| `factory-ledger-prototype-2026-11-15` | `br-still-river-bdh6nflp` | ready | **6** |
| `mcp-migration-2026-11-15T12-10-55` | `br-bitter-firefly-bd1jt928` | ready | **7** |

The six-table prototype contains:
`memory_projects`, `memory_missions`, `memory_decisions`, `memory_evidence`, `memory_checkpoints`, `memory_events`.

The seven-table prototype contains:
`memory_projects`, `memory_project_aliases`, `memory_decisions`, `memory_conversations`, `memory_artifacts`, `memory_work_items`, `memory_events`.

These are **two different public-schema memory prototypes**, not one canonical factory ledger. They must not be silently combined or treated as interchangeable.

A separate factory-specific draft exists in GitHub at `migrations/drafts/0001_factory_ledger.sql`. It defines the `factory` schema and seven operational tables: projects, tasks, task_attempts, task_events, task_approvals, task_artifacts, and task_evidence. Its CI checks passed against disposable PostgreSQL 17. It has **not** been applied to Neon.

The newer `migrations/0001_memory_gateway.sql` defines a different six-table memory schema and a read-only bootstrap function. It is a source artifact on PR #3, not a Neon migration already applied. No canonical schema choice has been finalized.

**Production boundary:** the Production branch is ready and has no application tables. No Production migration or write was performed in this audit. Keep it untouched.

## 4. Object storage (Backblaze B2)

[Run 43745900128](https://github.com/grinlife4-stack/TRADIX/actions/runs/43745900128) completed successfully on 2026-11-15:
- authenticated private-bucket access and object listing passed;
- upload and read-back test passed;
- the unique health-check object was intentionally retained.

This proves connectivity from an ephemeral GitHub-hosted runner. It does **not** prove a persistent runtime artifact lifecycle, metadata integration, retention workflow, backup, or restore. The PR #2 demo's own event/artifact output was not persisted to Neon or B2.

## 5. Implemented versus not operational

### Verified / implemented
- Strict task-envelope validation and evidence-gated state-transition contract.
- Provider-neutral model request/response contract and strict JSON plan parser; tests use a fake provider.
- Deterministic fixture demo that copies a reviewed template, runs tests, applies static rules, and emits evidence.
- Python CI and disposable PostgreSQL 17 negative integrity tests for the separate `factory` ledger draft.
- B2 adapter and one successful authenticated list/write/read-back connectivity test.
- PR #3 source artifacts for a memory gateway, schemas, and executive-runtime architecture.

### Not yet operational
- Live model provider/API credential, verified spend limit, or live model execution.
- Persistent orchestrator or worker that claims and executes real user tasks.
- Canonical Neon factory ledger selected, migrated, and used by the runtime.
- Tested execution of `migrations/0001_memory_gateway.sql`.
- Runtime integration test for `runtime/memory-gateway/index.mjs`.
- Persistent artifact lifecycle using B2, plus backup and restore verification.
- Automatic leases, heartbeats, retries, takeover, checkpoints, and stale-worker fencing.
- Independent semantic AI review; the demo review was deterministic static rules.
- Deployed TRADIX runtime/API or autonomous deployment.
- Repeated end-to-end operation with fault injection and recovery.

## 6. Current blockers and risks

1. **Schema divergence:** two existing `public.memory_*` prototypes differ; a separate `factory.*` ledger draft also exists. Choose and document one canonical responsibility boundary before any Neon migration.
2. **CI coverage gap:** PR #3's passing SQL workflow tests the older `factory` draft, not its new memory-gateway migration; the Node gateway has no demonstrated integration test.
3. **No persistent executor:** current ChatGPT/tool use is an interactive control path, not a continuously running autonomous factory.
4. **No live model budget:** a model adapter interface is not a connected model provider.
5. **No durable artifact/restore proof:** B2 connectivity is verified, backup/restore is not.
6. **Governance:** observed branches are not protected; draft PRs require human review and explicit merge approval.

## 7. Final operating decision

- Keep Neon `production` unchanged.
- Do not merge PR #2 or #3 automatically.
- Do not apply either memory migration to Neon yet.
- Treat the `factory` ledger draft as the strongest current candidate for operational task/event tracking because it explicitly models tasks, attempts, approvals, artifacts, evidence, idempotency, and immutable event records, and its disposable PostgreSQL checks passed. This is a recommendation for review, **not an approved migration**.
- Keep memory/context retrieval separate from the operational task ledger. The memory gateway is not a replacement for task execution state.
- Next engineering gate: reconcile the schemas, choose the canonical schema boundary, then add disposable-PostgreSQL tests for the PR #3 memory-gateway migration and a real integration test for the Node gateway before any isolated Neon trial.

## 8. Update protocol

This file is a dated snapshot. On every substantive work session, update it with:
- exact branch and commit SHA;
- PR state and CI run IDs/results;
- database branch/schema changes;
- artifacts and external side effects;
- completed tests and unverified claims;
- blockers, approvals required, and one next action.

Never mark work operational because a design, migration file, or adapter exists. Operational means the real execution path ran and its result was independently verified.


## 9. Verified implementation update — 2026-11-16

This section supersedes the earlier statements above that the memory-gateway migration and Node gateway had not been tested.

**Current tested source head:** `9d582902e63aa527043edc311dcda53f10ea1730`  
**PR:** [#3 — still Draft and unmerged](https://github.com/grinlife4-stack/TRADIX/pull/3)

### Added implementation
- Added `runtime/memory-gateway/server.mjs`, a Node.js HTTP adapter that exposes the existing read-only gateway handler as a runnable service.
- Added explicit local PostgreSQL TLS-mode support. TLS remains required by default; `sslmode=disable` is an explicit opt-in for disposable local/test databases only.
- Added `tests/test_memory_gateway_sql.sh` for disposable PostgreSQL schema, bootstrap, append-only, and idempotency checks.
- Added `tests/test_memory_gateway_integration.mjs` for health, authorization, missing-project, invalid-key, and successful context retrieval.
- Extended `.github/workflows/factory-ledger-sql.yml` to apply and test both draft schemas in disposable PostgreSQL 17, then run the Node HTTP integration test against that database.
- The first integration attempts exposed two real test issues: the test runner's PostgreSQL instance did not offer TLS, and the missing-project test accidentally queried the seeded project. Both were corrected and the final run passed.

### CI evidence on the tested source head
- [Python tests — run 43812745634](https://github.com/grinlife4-stack/TRADIX/actions/runs/43812745634): completed successfully.
- [Factory ledger + memory gateway SQL and HTTP integration — run 43812745635](https://github.com/grinlife4-stack/TRADIX/actions/runs/43812745635): completed successfully.
  - Existing factory ledger SQL tests passed.
  - Memory gateway migration applied successfully to disposable PostgreSQL 17.
  - Memory gateway SQL invariants passed: bootstrap, append-only event mutation rejection, and idempotency uniqueness.
  - Node HTTP integration passed: health endpoint, unauthorized request, missing project, invalid project key, and authenticated context retrieval.
- The successful integration proves the tested Node/PostgreSQL path in CI. It does **not** prove deployment, production hardening, Neon connectivity, persistent operation, or autonomous orchestration.

### Runtime and safety status
- The memory gateway now has a runnable Node entrypoint and passing disposable-database integration evidence.
- Neon Production remains untouched; no Neon migration was applied.
- The separate factory operational ledger remains a draft; no canonical production schema has been approved.
- PR #2 and PR #3 remain unmerged. No deployment, paid infrastructure, secret change, or Production write was performed.

### Next gate
Before any Neon trial: review and approve the schema responsibility boundary, add deployment/runtime configuration and secret handling, then run a controlled isolated Neon branch trial. Production remains prohibited until that trial and its recovery/security checks pass.


## 10. Final verification after runtime documentation — 2026-11-16

The memory gateway package now includes an `npm start` script and `runtime/memory-gateway/README.md` documents startup, required environment, TLS policy, API responses, and the read-only boundary.

**Latest fully tested branch head:** `9747796858895313e5eedc2712ed52c7a597f71e`

- [Python tests — run 43812887056](https://github.com/grinlife4-stack/TRADIX/actions/runs/43812887056): success.
- [Factory ledger + memory gateway SQL/HTTP integration — run 43812887095](https://github.com/grinlife4-stack/TRADIX/actions/runs/43812887095): success.
- Both runs completed successfully on the latest implementation/documentation head. The PostgreSQL job applied both draft schemas only to disposable PostgreSQL 17 and passed the factory-ledger tests, memory schema invariants, and Node HTTP integration.

The tested component is now a runnable, read-only memory gateway with repeatable CI evidence. It is still not deployed and is not yet connected to Neon. No Production changes have been made.


## 11. Verification of consolidated status record — 2026-11-16

The consolidated status record itself and all files on branch head `d2fb04959ebb1c0894d2d63605ea67f830441c27` were checked by CI:
- [Python tests — run 43812956896](https://github.com/grinlife4-stack/TRADIX/actions/runs/43812956896): success.
- [Factory ledger + memory gateway SQL/HTTP integration — run 43812956911](https://github.com/grinlife4-stack/TRADIX/actions/runs/43812956911): success.

The latest tested head therefore includes the status record, runnable package command, README, Node HTTP adapter, memory migration tests, and integration coverage. The test scope remains disposable PostgreSQL and CI only.
