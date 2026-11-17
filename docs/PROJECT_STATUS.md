# TRADIX — Project Status

**Snapshot:** 2026-11-17  
**Repository:** `grinlife4-stack/TRADIX`  
**Active PR:** [#9 — Worker lease fencing and portability gate](https://github.com/grinlife4-stack/TRADIX/pull/9)  
**Working branch:** `factory/worker-lease-fencing-v0-1`  
**Current branch head:** `0d777c097d6220eb1679fe856ac32cd93b6979a9`  
**Safety boundary:** PR #9 remains Draft and unmerged. No Neon or Production migration has been applied.

## 1. Executive status

TRADIX has a tested first software-product execution path, a PostgreSQL-backed factory ledger draft, and a verified Worker lease/fencing vertical slice on this branch.

TRADIX is **not yet an autonomous general-purpose factory**. The current executor runs trusted Node.js product code; it is not an OS sandbox. Automatic stage-level crash recovery is deliberately disabled until durable checkpoints and side-effect reconciliation exist.

## 2. Latest CI evidence

On branch head `0d777c097d6220eb1679fe856ac32cd93b6979a9`:

- [`factory-first-run` — run 44014670644](https://github.com/grinlife4-stack/TRADIX/actions/runs/44014670644): success.
- [`tests` — run 44014670601](https://github.com/grinlife4-stack/TRADIX/actions/runs/44014670601): success.
- [`factory-ledger-sql` — run 44014670619](https://github.com/grinlife4-stack/TRADIX/actions/runs/44014670619): all reported job steps completed successfully; final workflow conclusion was still being reported by GitHub when this snapshot was written.

Earlier fully completed Worker baseline on `52c96fbd13442396927115e57d13adcb615c9569` passed all three workflows, including PostgreSQL 17 migration, fencing SQL, runtime execution, and process-tree termination.

The current Python tests exercise the portability design/release gate. The first-run workflow validates the portability JSON Schema and verifies that the product dossier API persists the portability reference. The PostgreSQL workflow applies migrations 0001–0004 only to disposable PostgreSQL 17.

## 3. Worker lease/fencing implementation

Implemented and tested on this branch:

- `migrations/drafts/0004_worker_lease_fencing.sql`: per-task monotonic fencing counters, task leases, queued-attempt trigger, acquisition, renewal, assertion, fenced transition/evidence/finish, and lease release.
- `migrations/preflight/0004_worker_lease_fencing.sql`: privileged, read-only rollout preflight for active legacy work.
- `runtime/factory-executor/runner.mjs`: per-process worker identity, lease acquisition, bounded heartbeat, fenced writes, atomic terminal finalization, and process-tree termination.
- `tests/test_worker_lease_fencing_sql.sh`: PostgreSQL identity, concurrency, expiry, stale-write, approval, idempotency, and rollback tests.
- `.github/workflows/factory-ledger-sql.yml`: disposable database migration and runtime integration path.

Verified invariants include:
- A new lease epoch receives a monotonically increasing fencing token; same-worker retry while the lease is live is idempotent.
- Heartbeat and fenced writes validate the exact task/attempt/worker/token tuple and expiry.
- Task and lease locks serialize writes against takeover.
- Stale workers cannot transition tasks, record evidence, finish attempts, or replay old idempotency keys.
- Database lease acquisition independently enforces exact-attempt, exact-scope human approval where required.
- Evidence is rejected after attempt completion; terminal task transitions require a matching terminal attempt outcome.
- Lease tables are inaccessible directly to runtime; legacy unfenced write functions are revoked; PUBLIC execution on lease APIs is revoked.
- Attempt completion, terminal task transition, and lease release are atomic.
- Runner refuses unsafe implicit recovery and terminates descendant processes after lease loss.

## 4. Product portability gate

A first machine-enforced portability contract now exists:

- `schemas/product-portability-v1.schema.json`: versioned manifest schema.
- `scripts/check_product_portability.py`: design and release assessment modes; strict field validation; secret exclusion; dependency adapter/replacement requirements; relative evidence paths; and actual SHA-256 verification of evidence files.
- `docs/PRODUCT_PORTABILITY_GATE.md`: usage and limitations.
- `examples/hello-world/portability.json`: initial product portability plan.
- `schemas/product-dossier-v1.schema.json` and `examples/hello-world/product.json`: optional dossier link to the portability manifest.

The Hello World manifest is deliberately **design-ready but not release-ready**. CI verifies that design validation passes and release validation stays blocked. A release cannot pass until verified export/import procedures, file-backed evidence, a successful restore on a second isolated host, and an evidenced exit-cost estimate exist.

This gate validates submitted evidence files and hashes. It does not itself perform database exports, object-storage migration, or cross-host restore.

## 5. Explicit limitations and safety boundaries

- Migration 0004 is still a draft. It has **not** been applied to Neon or Production.
- PR #9 is open, Draft, and unmerged. Green CI is not merge authorization.
- The runner refuses interrupted non-queued tasks. Database lease takeover exists, but automatic stage-level resume does not.
- Durable checkpoints, stage idempotency contracts, and external side-effect reconciliation remain unimplemented.
- `trusted-node` execution is not a sandbox. Only reviewed, trusted product code may run through it.
- A complete backup/export/import and restore rehearsal on a second host remains unimplemented.
- Live model-provider integration, spend enforcement, persistent unattended orchestration, and autonomous multi-product operation remain incomplete.

## 6. Next execution sequence

1. Keep PR #9 Draft until the migration, runner, tests, and portability changes receive review. Do not merge automatically.
2. Keep Neon Production untouched. Any isolated Neon trial requires separate explicit approval after reviewing role ownership, ACLs, RLS, and migration preflight.
3. Implement real product export/import for source, ledger data, artifacts, and evidence; then rehearse a complete restore on a second isolated host and verify hashes, permissions, and product history.
4. Add stage-level recovery only after durable checkpoints, idempotent stage contracts, and side-effect reconciliation can be tested.
5. Keep the executor classified as trusted-code execution until an actual OS/container sandbox enforces resource, filesystem, network, and secret boundaries.

This file records verified state, not intended capability. A design document, configured integration, or green unit test alone does not prove a production deployment or a completed recovery path.
