# Worker Lease and Fencing Contract v0.1

Status: proposed implementation contract  
Target branch: `factory/worker-lease-fencing-v0-1`  
Base: `factory/executive-runtime-architecture-v0-1`  
Scope: PostgreSQL task execution ownership and crash recovery. This document does not authorize applying migrations to Neon or Production.

## 1. Problem

The current ledger creates attempts with status `running` before a worker has acquired exclusive execution ownership. Lifecycle transitions, evidence writes, and attempt completion identify an attempt but do not prove that the caller still owns execution. A timed-out or partitioned worker can therefore continue writing after another worker has taken over.

A lease table alone is insufficient. Every write path that can change execution state or produce trusted evidence must enforce the current fencing token inside PostgreSQL.

## 2. Required invariants

1. At most one unexpired lease exists for a task.
2. Lease acquisition and takeover are serialized by locking the task row.
3. Every successful acquisition or takeover receives a strictly increasing fencing token for that task. Tokens are never reused, including after lease deletion or expiry.
4. A lease is bound to `task_id`, `attempt_id`, `worker_id`, token, and expiry.
5. Heartbeat, lifecycle transition, evidence recording, and attempt completion must validate the exact current tuple and require `expires_at > clock_timestamp()`.
6. Fenced write validation must lock the task row and then the lease row, in the same order as acquisition, and hold those locks through the delegated write. This prevents a takeover from interleaving between validation and mutation.
7. Validation occurs before idempotency replay. A stale worker cannot obtain a successful response by replaying an old idempotency key.
8. Once takeover succeeds, every write from the former worker fails, even if its process is still running.
9. Expiry alone does not create a new owner. A new owner exists only after a successful serialized acquisition.
10. Only the product's isolated runtime LOGIN may acquire or renew its product's leases. Runtime roles cannot write lease tables directly.
11. Human approval remains a separate authority and cannot acquire worker leases.

## 3. Database API

The migration must provide narrowly scoped SECURITY DEFINER functions:

- `acquire_task_lease(task_id, attempt_id, worker_id, ttl_seconds)` returns the fencing token and expiry. It locks the task, verifies product ownership and attempt state, rejects a different live owner, and performs a monotonic token increment on first acquisition or takeover.
- `renew_task_lease(task_id, attempt_id, worker_id, fencing_token, ttl_seconds)` extends only the exact live lease for a running attempt. It must not revive an expired lease or extend a completed attempt.
- `assert_task_lease(task_id, attempt_id, worker_id, fencing_token)` is an internal helper callable only by the trusted function owner.
- Fenced lifecycle transition, evidence, and attempt-finish APIs require the fencing token and invoke the lease assertion before any idempotency lookup or write.
- The previous unfenced runtime write functions must be revoked from runtime roles. No compatibility path may bypass fencing.
- Lease state is private to the database API. Product runtimes receive no direct SELECT, INSERT, UPDATE, DELETE, or TRUNCATE rights on lease tables.

A per-task monotonically increasing counter must survive lease-row deletion. A global sequence is acceptable if the API guarantees monotonicity and does not expose sequence mutation to runtime roles.

## 4. Attempt lifecycle and recovery

Attempt creation must produce a `queued` attempt, not an already-running attempt. Acquisition changes it to `running` and records `started_at`.

At the database layer, a worker may reacquire the same attempt after its prior lease expires. The new acquisition receives a higher fencing token. The current runner deliberately does **not** resume intermediate task states: it accepts only a `queued` task with a `queued` attempt, and refuses all interrupted states. This prevents unsafe re-execution of scripts that may have external side effects.

Stage-level recovery remains unsupported until durable checkpoints, stage idempotency contracts, and side-effect reconciliation exist. Do not describe lease takeover as automatic crash recovery. An interrupted attempt requires an explicit operator recovery decision or a separately designed recovery protocol.

A takeover must not silently mark the previous worker successful. The attempt remains the same logical attempt, while the new lease epoch fences all work from the previous process. If policy later requires a new attempt per takeover, that is a separate schema/API decision and must preserve the same fencing guarantee.

Lease release/completion must be atomic with terminal attempt completion. A failed or lost connection must never leave a succeeded attempt with a non-terminal task, or a verified task with an unsuccessful attempt.

## 5. Runner contract

- Generate a stable worker identity per process instance; do not reuse it across independent workers.
- Acquire before executing product code.
- Keep the returned fencing token in process memory and pass it to every database write.
- Heartbeat at a bounded fraction of the lease TTL, with a bounded query timeout. If renewal fails, stop launching work and terminate the entire child process tree.
- Do not treat a local timeout as proof that the child process stopped. Kill the process tree and await the stage leader's termination before cleanup.
- On restart, fail closed for any non-queued task/attempt state. Do not resume until durable stage checkpoints and side-effect safety are implemented.
- The runner must never fall back to an unfenced database function.
- Keep the existing `trusted-node` warning: leases coordinate workers; they are not an OS sandbox.

## 6. Required CI tests

Run against disposable PostgreSQL 17 and isolated product LOGIN identities:

1. First acquisition returns a token; a second worker cannot acquire while the lease is live.
2. A heartbeat extends the exact lease; wrong worker, attempt, token, and expired lease are rejected.
3. After expiry, takeover succeeds with a strictly greater token.
4. The former worker is rejected for transition, evidence, finish, and idempotent replay after takeover.
5. The current worker can transition, record evidence, and finish.
6. Concurrent acquisition attempts serialize and produce exactly one current owner.
7. An in-flight fenced evidence write holds the task/lease locks so an expired-lease takeover cannot commit ahead of that write.
8. Runtime cannot mutate lease rows or invoke legacy unfenced write APIs.
9. Product A cannot inspect or mutate Product B lease state, including acquire and renew calls.
10. Runner refuses a non-queued interrupted task/attempt rather than rerunning side-effectful stages.
11. Terminal completion and lease release commit or roll back as one transaction under injected failure.

## 7. Migration and rollout constraints

- Implement as a new forward-only migration after the currently applied draft migrations; do not rewrite the existing migration history.
- Update the disposable PostgreSQL CI workflow to apply the migration before the ledger tests and executor integration test.
- Update SQL tests and runner in the same pull request.
- Do not apply this draft migration to Neon or Production until CI passes, the diff is reviewed, and a separate explicit rollout decision is made.
- Do not merge this branch automatically. Open a draft PR only after the migration, tests, runner, and documentation are complete.
