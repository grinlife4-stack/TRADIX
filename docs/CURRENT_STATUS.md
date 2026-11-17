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
- PR #5 (blanket pending-approval restriction) was closed without merge after CI showed it broke the trusted Hello World onboarding executor. It is a rejected experiment, not an accepted fix.
- PR #7 adds a dedicated `factory_onboarding_authority` marker: ordinary product runtimes may write only `pending_approval` dossiers; the isolated onboarding runner retains its tested first-run path. PR #7 is open, Draft, and unmerged. Exact head `a345f9b194ff3f9d96c7fbc13022e583f5de03c1`; Python and PostgreSQL/HTTP CI both passed on that head.
- PR #8 adds committed npm lockfiles and changes the Node integration workflow to `npm ci`. It is open, Draft, and unmerged. Code-bearing head `412ddd3f9a49ed5467684da7937efe20345ec822`; Python tests and full PostgreSQL/HTTP integration CI both passed on that head. Subsequent commits on this branch after that CI run contain status-documentation updates only; no code, workflow, lockfile, or test changed.
- `main` was not changed by the maintenance work. Its protection status was reported as disabled during inspection; do not assume branch protection enforces review or CI gates.

## 2. Implemented and verified boundaries

- Provider-neutral mission, task, and plan contracts with validation tests.
- PostgreSQL draft ledger with project isolation, RLS, controlled SECURITY DEFINER write paths, idempotency, append-only version snapshots, and disposable PostgreSQL integration tests.
- Product dossier versioning and mission/task-plan version APIs. PR #7's role-separated dossier lifecycle restriction is CI-verified on disposable PostgreSQL, but not merged or deployed.
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

## 4. Additional lifecycle gap found

- Atomic `POST /v1/intake` enforces pending human approval for dossier + mission + task-plan snapshots.
- PR #7 closes the direct active-dossier bypass for ordinary runtime identities while preserving the isolated factory onboarding identity. CI passed; merge and deployment have not occurred.
- A complete approval-decision writer and approved-plan-to-task path are still missing. Dossiers remain pending; the system cannot yet promote approved intake plans into executable tasks.

## 5. Maintenance branch

- Maintenance branch: [`maintenance/repository-slimdown-v0-1`](https://github.com/grinlife4-stack/TRADIX/tree/maintenance/repository-slimdown-v0-1).
- The superseded software-only master plan was moved to `docs/archive/`; its content was preserved.
- The architecture baseline was renamed to `docs/FACTORY_ARCHITECTURE_BASELINE_V1_2.md`, matching its declared version 1.2.
- The large historical log remains in `docs/PROJECT_STATUS.md`; this file is now the concise current snapshot.
- Maintenance changes include documentation organization, package metadata, generated-file exclusions, three npm lockfiles, and the Node integration workflow's switch to `npm ci`. No runtime source code, database schema/migration, credentials, or deployment was changed. PR #8's Python and PostgreSQL/HTTP CI passed on its exact head.

## 6. Next engineering gates

1. Implement worker ownership, leases, fencing, and stale-write rejection as one database-enforced lifecycle path; close all bypass writes and test concurrency, expiry, crash, and takeover.
2. Add the explicit approval-decision path; only approved, version-matched plans may become executable tasks.
3. Pin or lock the Python development and storage dependency sets; `pyproject.toml` still uses open-ended lower bounds for `pytest`, `setuptools`, and `boto3`.
4. Prove backup and restore, not merely object-store connectivity.
5. Add a real isolation boundary before any untrusted product code can execute.
6. Obtain independent review of PR #3, re-check exact-head CI and mergeability, then decide whether it is ready to leave Draft.

## 7. Safety and change record

- No Neon schema migration or Production database write was performed.
- No secrets or repository permissions were changed.
- No deployment, merge, paid resource, or worker execution was initiated.
- Historical implementation and CI details remain in [`PROJECT_STATUS.md`](PROJECT_STATUS.md); use this file for current state and inspect live GitHub refs before acting.
