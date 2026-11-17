# TRADIX — Project Status

**Snapshot:** 2026-11-17  
**Repository:** `grinlife4-stack/TRADIX`  
**Active PR:** [#9 — Worker lease fencing](https://github.com/grinlife4-stack/TRADIX/pull/9)  
**Working branch:** `factory/worker-lease-fencing-v0-1`  
**Last fully verified head:** `52c96fbd13442396927115e57d13adcb615c9569`  
**Safety boundary:** PR remains Draft and unmerged. No Neon or Production migration has been applied.

## 1. Executive status

TRADIX has a tested first software-product execution path and a PostgreSQL-backed factory ledger draft. The Worker lease/fencing vertical slice is now implemented on the draft branch and passes its disposable PostgreSQL and runtime CI checks.

TRADIX is **not yet an autonomous general-purpose factory**. The current executor runs trusted Node.js product code; it is not an OS sandbox. Automatic stage-level crash recovery is deliberately disabled until durable checkpoints and side-effect reconciliation exist.

## 2. Latest verified CI

All three workflows passed on the exact head `52c96fbd13442396927115e57d13adcb615c9569`:

- [`factory-ledger-sql` — run 44013385920](https://github.com/grinlife4-stack/TRADIX/actions/runs/44013385920): success. Applies drafts 0001–0004 to disposable PostgreSQL 17, runs the migration preflight and lease/fencing SQL tests, and exercises the factory executor.
- [`factory-first-run` — run 44013386007](https://github.com/grinlife4-stack/TRADIX/actions/runs/44013386007): success.
- [`tests` — run 44013385933](https://github.com/grinlife4-stack/TRADIX/actions/runs/44013385933): success.

The PostgreSQL workflow verifies:
- Migration 0004 refuses to adopt active legacy tasks and applies only after the fixture is drained.
- Attempts begin queued and become running only after lease acquisition.
- Database-level approval checks bind approval to the exact task, attempt, action, and decision scope.
- A human approval identity cannot acquire a worker lease; an approved runtime can.
- Same-worker repeated acquisition is idempotent; new ownership epochs use increasing fencing tokens.
- Wrong worker, attempt, token, product identity, expired lease, and stale worker writes are rejected.
- Validation locks the task and lease in a consistent order; takeover cannot interleave with an in-flight evidence write.
- Evidence cannot be appended after attempt completion; terminal task transitions require the matching terminal attempt outcome.
- Runtime cannot call legacy unfenced write functions or access lease tables directly; PUBLIC execution on lease APIs is revoked.
- Completion, terminal transition, and lease release roll back or commit atomically.
- The runner executes Hello World, validates an idempotent retry, blocks unapproved high-risk work, and terminates descendant processes after lease loss.

## 3. Implemented on the draft branch

- `migrations/drafts/0004_worker_lease_fencing.sql`: per-task monotonic fencing counters, task leases, queued-attempt trigger, acquisition, renewal, assertion, fenced transition/evidence/finish, and lease release.
- `migrations/preflight/0004_worker_lease_fencing.sql`: privileged, read-only rollout preflight for active legacy work.
- `runtime/factory-executor/runner.mjs`: per-process worker identity, lease acquisition, bounded heartbeat, fenced writes, atomic terminal finalization, and process-tree termination.
- `tests/test_worker_lease_fencing_sql.sh`: PostgreSQL 17 identity, concurrency, expiry, stale-write, approval, idempotency, and rollback tests.
- `.github/workflows/factory-ledger-sql.yml`: disposable database migration and runtime integration path.
- `docs/WORKER_LEASE_FENCING_SPEC.md` and executor README: lifecycle, security, and recovery boundaries.

## 4. Explicit limitations

- Migration 0004 is still a draft. It has **not** been applied to Neon or Production.
- PR #9 is open, Draft, and unmerged. Green CI is not merge authorization.
- The runner refuses interrupted non-queued tasks. Lease takeover exists at the database layer, but automatic stage-level resume does not.
- Durable checkpoints, stage idempotency contracts, and external side-effect reconciliation remain unimplemented.
- `trusted-node` execution is not a sandbox. Only reviewed, trusted product code may run through it.
- The portability charter exists, but a machine-enforced portability gate and a complete cross-host backup/restore proof are not yet implemented.
- Live model-provider integration, spend enforcement, persistent unattended orchestration, and autonomous multi-product operation remain incomplete.

## 5. Next execution sequence

1. Keep PR #9 Draft until the migration, runner, SQL tests, and CI evidence receive review. Do not merge automatically.
2. Keep Neon Production untouched. Any isolated Neon trial requires a separate explicit approval after reviewing role ownership, ACLs, RLS, and migration preflight.
3. Implement the portability gate from `docs/FREEDOM_AND_PORTABILITY_CHARTER.md`: dependency/adapter inventory, inspectable data and artifact export, secret separation, documented restore procedure, and a real restore test on a second isolated host.
4. Design stage-level recovery only after checkpoints, idempotent stage contracts, and side-effect reconciliation can be tested.
5. Keep the executor classified as trusted-code execution until an actual OS/container sandbox with enforced resource, filesystem, network, and secret boundaries is implemented.

This file records verified state, not intended capability. A design document, configured integration, or green unit test alone does not prove a production deployment or a completed recovery path.
