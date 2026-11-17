# TRADIX — Current Status

**Snapshot:** 2026-11-17  
**Canonical integration PR:** [#3 — Define TRADIX executive runtime architecture](https://github.com/grinlife4-stack/TRADIX/pull/3)  
**Main branch at inspection:** `d778e6e5c15eea353355d38c681b49a00dca1da7`  
**Production policy:** No Neon Production migration, production write, deployment, secret change, or paid-service action is authorized by this status note.

## 1. Integration state

- PR #3 is the canonical integration PR. It is **open, Draft, and unmerged**, targeting `main`.
- PR #3 head at inspection: `ef3786607fb825b7f119e7d52541c10529efedd6`.
- GitHub currently reports `mergeable=true`; this is not approval to merge.
- No PR reviews were submitted at inspection.
- All three CI checks on the exact PR #3 head completed successfully:
  - Python tests: [43938849739](https://github.com/grinlife4-stack/TRADIX/actions/runs/43938849739)
  - Factory first-run: [43938849723](https://github.com/grinlife4-stack/TRADIX/actions/runs/43938849723)
  - Factory ledger SQL/HTTP integration: [43938849718](https://github.com/grinlife4-stack/TRADIX/actions/runs/43938849718)
- PR #2 and PR #4 are closed and unmerged; they are superseded, not release artifacts.
- `main` was not changed by the maintenance work. Its protection status was reported as disabled during inspection; do not assume branch protection enforces review or CI gates.

## 2. Implemented and verified boundaries

- Provider-neutral mission, task, and plan contracts with validation tests.
- PostgreSQL draft ledger with project isolation, RLS, controlled SECURITY DEFINER write paths, idempotency, append-only version snapshots, and disposable PostgreSQL integration tests.
- Product dossier versioning and mission/task-plan version APIs.
- Atomic product intake persists dossier + mission + task-plan snapshots in one transaction and stops at pending human approval.
- Deterministic first-run demo executes reviewed fixture templates and produces test/review/evidence artifacts; it does not call a live model.
- Read-only memory gateway is separate from the operational task ledger.
- Backblaze B2 workflow verifies connectivity and object read-back only; it does not prove artifact lifecycle recovery or backup/restore.

## 3. Not operational yet

- Atomic worker claim, expiring lease, heartbeat, fencing-token enforcement, stale-worker rejection, bounded retries, and restart/takeover recovery.
- Approval-decision write path and conversion of approved plans into executable tasks.
- Persistent dispatch/orchestration and unattended worker operation.
- Live model-provider execution, model credentials, and verified hard spend limits.
- OS-level sandboxing for untrusted product code. The current Node executor is explicitly trusted-code-only.
- Production deployment, production migration, and tested backup/restore.

A green disposable-database CI run is not evidence that any of these missing capabilities is operational.

## 4. Maintenance branch

- Maintenance branch: [`maintenance/repository-slimdown-v0-1`](https://github.com/grinlife4-stack/TRADIX/tree/maintenance/repository-slimdown-v0-1).
- The superseded software-only master plan was moved to `docs/archive/`; its content was preserved.
- The architecture baseline was renamed to `docs/FACTORY_ARCHITECTURE_BASELINE_V1_2.md`, matching its declared version 1.2.
- The large historical log remains in `docs/PROJECT_STATUS.md`; this file is now the concise current snapshot.
- Maintenance changes are documentation-only. No runtime tests were run on this branch, and no maintenance-branch CI result is claimed.

## 5. Next engineering gates

1. Complete dependency reproducibility: generate and commit package lockfiles for each independently deployable Node package, then change CI from `npm install` to `npm ci`. Do not hand-author lockfiles.
2. Implement worker ownership, leases, fencing, and stale-write rejection as one database-enforced lifecycle path; close all bypass writes and test concurrency, expiry, crash, and takeover.
3. Add the explicit approval-decision path; only approved, version-matched plans may become executable tasks.
4. Prove backup and restore, not merely object-store connectivity.
5. Add a real isolation boundary before any untrusted product code can execute.
6. Obtain independent review of PR #3, re-check exact-head CI and mergeability, then decide whether it is ready to leave Draft.

## 6. Safety and change record

- No Neon schema migration or Production database write was performed.
- No secrets or repository permissions were changed.
- No deployment, merge, paid resource, or worker execution was initiated.
- Historical implementation and CI details remain in [`PROJECT_STATUS.md`](PROJECT_STATUS.md); use this file for current state and inspect live GitHub refs before acting.
