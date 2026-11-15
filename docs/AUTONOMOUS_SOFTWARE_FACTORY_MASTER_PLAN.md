# Autonomous Software Factory — Master Execution Plan

**Document status:** Preflight status correction, version 0.2  
**Created:** 2026-11-15  
**Control repository:** `grinlife4-stack/TRADIX`  
**Branch:** `factory/preflight-status-2026-11-15`  
**Operating rule:** This document is the durable project ledger. Do not rely on chat memory as the source of truth.

## 1. Mission

Build a reusable, project-independent software factory that can accept a task, clarify requirements, inspect a codebase, plan work, implement changes, run independent tests and reviews, repair failures, deploy to an isolated environment, verify runtime behavior, and report evidence.

The factory must support multiple isolated projects, initially including TRADIX and info_engine. AAECN, XENORA, and other projects must remain separate namespaces and must not be modified unless explicitly selected.

The first milestone is not a large multi-agent system. It is one complete, repeatable, auditable software delivery loop.

## 2. Definition of done for the first working loop

Given a bounded task and a selected repository, the system must:

1. Read the repository and its project instructions.
2. Create a task record with a unique ID, scope, acceptance criteria, risks, and status.
3. Produce a short implementation plan before editing.
4. Create an isolated branch or worktree; never edit the production branch directly.
5. Implement the change and record the exact files changed.
6. Run formatting, static checks, unit tests, and relevant integration tests.
7. Have a reviewer process inspect the diff independently from the implementer.
8. If checks fail, diagnose and attempt bounded repairs; stop after a configured retry limit.
9. Produce a release candidate with test logs, commit SHA, diff summary, and unresolved risks.
10. Deploy only to a non-production environment after policy checks.
11. Run post-deployment health checks and report the actual deployment result.
12. Require explicit human approval for production deployment, destructive data changes, secret changes, permission changes, and irreversible operations.

A task is not complete merely because code was generated or a deployment command returned success.

## 3. System architecture

### Control plane
- ChatGPT: human-facing interface, task intake, coordination, approval requests, and reporting.
- Factory Orchestrator: durable task state machine; dispatches bounded jobs to workers.
- Policy Gate: enforces permissions, retry limits, environment boundaries, and approval requirements.

### Execution plane
- Planner: turns requests into scoped tasks and acceptance criteria.
- Implementer: edits code in an isolated branch/workspace.
- Test Engineer: runs checks and creates reproducible test evidence.
- Independent Reviewer: inspects the diff, security, architecture, and test quality.
- Release Agent: deploys only approved candidates to the designated environment.
- Observer: checks runtime health, logs, metrics, and regressions.

Workers must not be able to silently approve their own work. Agents should receive the minimum permissions needed for their task.

### Systems of record
- GitHub: source code, branches, pull requests, reviews, CI, and immutable commit references.
- Neon: structured operational state, task metadata, approvals, execution records, and audit events.
- Backblaze B2: S3-compatible object-storage target; private bucket `tradix-factory-storage` verified from GitHub-hosted runner. Authenticated bucket listing and object write/read-back both passed in workflow run `43745900128`. This verifies connectivity only, not the factory artifact lifecycle or backup/restore.
- Railway: candidate runtime for API/worker deployment; account connection is verified, but no factory service is deployed yet.
- Sentry: optional error monitoring; not connected or configured yet.

### Model layer
Use a provider-independent adapter. Do not hard-code the factory to one model vendor. Keep model selection, cost limits, timeouts, and fallback policy configurable. Model output is untrusted input and must pass validation and policy checks.

## 4. Non-negotiable safety and reliability rules

1. Fail closed: if repository state, task state, evidence, or storage integrity cannot be verified, stop.
2. No direct production edits by workers.
3. No self-approval: implementation and review are separate roles.
4. No secrets in source code, prompts, public repositories, logs, or task artifacts.
5. Never print or copy database connection strings, API tokens, private keys, or secret values into chat or GitHub.
6. Production deployment, destructive migrations, deletion, permission changes, and irreversible actions require explicit approval.
7. Every action must record actor/agent, task ID, timestamp, target, input reference, result, and evidence reference.
8. Retries are bounded; repeated failure escalates to a human instead of looping indefinitely.
9. Tests must be relevant to the changed behavior. A passing smoke test is not proof of production readiness.
10. Backups are not considered valid until a restore test succeeds.
11. Separate project data, credentials, environments, and memory namespaces.
12. Do not claim an action succeeded until the corresponding tool or runtime result confirms it.

## 5. Current verified infrastructure

| Component | Verified state | Important limitation |
|---|---|---|
| GitHub | Connected; access to `grinlife4-stack/TRADIX` verified; push permission available | TRADIX currently has only a minimal package and smoke-test baseline; CI success is not proof of factory capability |
| Neon | Connected; production branch is ready and contains no application tables; isolated temporary branch contains seven `memory_*` tables | Those tables are project-memory structures, not yet approved as the factory task ledger; no factory schema or production migration has been performed |
| Cloudflare | Connected; authenticated account identity verified | Not selected as the current object-storage target; keep the connector for other Cloudflare services |
| Backblaze B2 | Private bucket `tradix-factory-storage`, region `us-east-005`; GitHub Actions run `43745900128` passed authenticated listing and object write/read-back | Connectivity verified from an ephemeral GitHub runner only; no persistent runtime artifact lifecycle or backup/restore test yet |
| Railway | Connected; authenticated user and personal workspace verified | Workspace currently reports zero projects; no service or deployment exists |
| Sentry | No Sentry connector tools exposed in the current tool inventory | Defer until a runtime service exists; revisit plugin availability later |
| Model provider adapter | Not implemented | Select providers only after defining security, cost, and fallback requirements |

Never place credentials in this public repository. The repository is public.

## 6. Execution phases and task ledger

Statuses: `NOT_STARTED`, `IN_PROGRESS`, `BLOCKED`, `DONE`, `VERIFIED`.

### Phase 0 — Establish the control record
- [x] Create this master plan on an isolated Git branch.
- [x] Open a pull request for review; PR merge remains a human-controlled action. (Historical PR #1 merged; this status-correction PR is separate.)
- [ ] Establish a factory-specific durable task/event schema and append-only execution ledger; do not reuse the temporary memory tables without a deliberate schema review.
- [x] Define initial task envelope and state-transition contract in `src/tradix/factory/task_contract.py`; persistence and approval records remain unimplemented.

### Phase 1 — Verify infrastructure and boundaries
- [x] Re-inspect GitHub repository branches, rulesets, and CI workflow. No repository rulesets are configured; `main` is not protected.
- [x] Inspect Neon production and temporary branch schemas separately; production has no user tables; temporary branch has seven `memory_*` tables. No migration performed.
- [x] Select Backblaze B2 instead of Cloudflare R2; user-created private bucket and endpoint metadata recorded.
- [x] Verify the five B2 settings through the manual GitHub Actions workflow without exposing secret values. Run `43745900128` completed successfully; read/list and write/read-back passed. The test object was retained by design.
- [x] Inspect published Railway pricing and workspace/project inventory. Public pricing lists Free at $0 with a 30-day $5 trial then a $1/month free tier; Hobby has a $5/month minimum and Pro $20/month. Account-specific plan/credits are not exposed by the connector. No project/service exists; cloud-agent connector listing returned an account capability error.
- [ ] Decide whether Railway is acceptable for the first non-production runtime; compare alternatives before committing.
- [ ] Define secret storage and runtime-to-Neon/B2 connectivity without exposing secret values.
- [ ] Defer Sentry until the first service can emit telemetry.

### Phase 2 — Build the smallest vertical slice
- [x] Select the first bounded task: validate task envelopes and enforce evidence-gated state transitions (pure Python, no external services).
- [x] Implement a pure state-transition contract with blocked/failed/cancelled handling; orchestration, retries, and persistence remain outside this first code slice.
- [ ] Implement a worker that reads task input and repository state but cannot deploy to production.
- [ ] Implement branch-scoped code changes and pull-request creation.
- [ ] Implement CI evidence collection and independent diff review.
- [ ] Demonstrate bounded repair after a deliberately introduced test failure.
- [ ] Demonstrate that missing evidence or storage failure blocks progression.

### Phase 3 — Runtime and persistence
- [ ] Deploy the orchestrator to an isolated Railway service only after runtime design and cost approval.
- [ ] Connect Neon using runtime-managed secrets; never expose connection strings.
- [ ] Add durable task, event, approval, artifact, and run records.
- [ ] Add health endpoint, structured logs, timeouts, cancellation, and bounded concurrency.
- [ ] Add backup export to Backblaze B2 and perform a restore test before declaring backup readiness.

### Phase 4 — Independent quality and security
- [ ] Separate planner, implementer, tester, reviewer, and release permissions.
- [ ] Add dependency/security scanning and secret scanning.
- [ ] Add test coverage thresholds appropriate to each project.
- [ ] Add reproducible build metadata and artifact hashes.
- [ ] Add model output validation, prompt-injection boundaries, and tool allowlists.
- [ ] Add Sentry or equivalent error monitoring after runtime exists.

### Phase 5 — Controlled delivery and multi-project support
- [ ] Add isolated project registry and per-project policies.
- [ ] Add environment-specific deployment gates.
- [ ] Add human approval workflow for production and destructive operations.
- [ ] Add rollback procedure and verify it in a test environment.
- [ ] Run a complete end-to-end acceptance test.
- [ ] Only then enable routine unattended execution for low-risk tasks.

## 7. Immediate next actions

1. Review the status-correction pull request; do not merge without user approval.
2. Select the first bounded, reversible software task and define exact acceptance criteria.
3. Resolve the persistent execution/runtime choice and model-provider credentials/cost before attempting autonomous multi-step execution.
4. Keep Neon production untouched; use an isolated branch for any schema prototype.
5. Implement a minimal task intake → isolated branch → CI → independent review → evidence report loop before adding deployment.

## 8. Required status report format

Every work session must update this file or a linked task record and report:

- **Completed:** actions confirmed by tool/runtime evidence.
- **Changed:** repository paths, commit SHAs, database objects, or service configuration changed.
- **Tests:** exact commands/checks and pass/fail outcomes.
- **Blocked:** missing permissions, dependencies, approvals, or evidence.
- **Risks:** unresolved security, reliability, cost, or operational concerns.
- **Next action:** one concrete action, with owner and prerequisite.
- **Approval required:** exact action awaiting user authorization.

Do not mark a task DONE or VERIFIED based on intention, generated code, or an unverified claim.

## 9. Change-control rule for this document

This file is the durable master checklist, not a chat summary. Update task status only when supported by evidence. Add dated execution notes or link to immutable commits, PRs, CI runs, and deployment IDs. Preserve unresolved items; do not silently remove them. Keep project-specific technical specifications in their own project repositories and link them here rather than copying them into a shared document.


## 10. Preflight evidence update — 2026-11-15

- Repository: `grinlife4-stack/TRADIX`; `main` remains at `d778e6e5c15eea353355d38c681b49a00dca1da7` at the time of inspection.
- Branches observed before this documentation PR: `main`, `factory/phase-0-blueprint`; the new documentation branch is `factory/preflight-status-2026-11-15`. No rulesets returned by GitHub rulesets endpoint; the observed branches report `protected=false`.
- Pull request #1 is closed and merged. Its CI run `43739714859` passed.
- B2 workflow run `43745900128` completed successfully. Job logs confirmed `WRITE_TEST=true`, `B2_AUTH_AND_BUCKET_READ=PASS`, `OBJECTS_VISIBLE_IN_SAMPLE=0`, and `B2_WRITE_AND_READBACK=PASS`. The unique health-check object remains in the bucket because version retention is enabled.
- Neon project `royal-art-56263739`: production branch `br-lingering-hall-bdh0g9if` is ready and has zero application tables; temporary branch `br-bitter-firefly-bd1jt928` is ready and has seven `memory_*` tables. Both branch records report `protected=false`. No production writes or migrations were performed.
- Railway is connected; workspace `Grin Life's Projects` has zero projects. `whoami` exposes no plan/credit details. Published pricing: Free $0 (30-day trial with $5 credits, then $1/month per pricing page), Hobby $5/month minimum, Pro $20/month minimum; actual resource and agent model usage can add charges. The agent-connector listing was not available to this account; do not assume it can provide an execution environment.
- GitHub connector exposes branch/file/commit/PR write operations. It does not expose a direct workflow-dispatch operation in the current tool inventory. CI can still run automatically on a PR or push according to workflow triggers.
- Sentry connector tools were not present in the current tool inventory.
- No model-provider API credential or persistent orchestrator has been verified. ChatGPT subscription access must not be treated as an API key or an included external model budget.
- Documentation correction is proposed in draft PR #2: https://github.com/grinlife4-stack/TRADIX/pull/2. It does not deploy a service, alter database schemas, change secrets, modify branch protection, or merge to `main`.

- Public Railway pricing references checked: https://railway.com/pricing and https://docs.railway.com/pricing/free-trial. Account-specific trial eligibility, remaining credits, billing method, and spending caps remain unverified; no Railway resource was created.


## 11. First code slice — task contract

The first implementation slice is deliberately provider-free and persistence-free. It establishes strict task-envelope validation and a finite state-transition graph with evidence gates. It does not call an LLM, create branches, write Neon, upload B2 artifacts, or deploy services. Those are later integrations and must not be represented as already working.

The temporary Neon branch's seven `memory_*` tables were inspected at the column/constraint level. They represent project memory, work items, artifacts, conversations, decisions, aliases, and memory events. They are not yet accepted as the factory's operational ledger: the event table has no demonstrated append-only enforcement, and the work-item model does not provide the full execution/approval/evidence semantics. Production remains untouched.

The next integration gate is to prove this contract in CI, then design a separate factory ledger schema and an actual execution adapter. The current GitHub Actions workflow runs tests only; it is not an autonomous code-generation agent.


## 12. Code slice execution record — 2026-11-15

- Added `src/tradix/factory/task_contract.py` and package initializer; the contract is pure Python and performs no external I/O.
- Added `tests/test_task_contract.py` for task validation, fail-closed unknown fields, risk approval, legal transitions, and evidence gates.
- Added `docs/FIRST_VERTICAL_SLICE_SPEC.md` to state the scope and explicit exclusions.
- Hardened direct construction and transition calls against invalid runtime types.
- CI runs for earlier commits in this PR passed (`43747264790`, `43747257944`, `43747255688`). The latest hardening commit `572c44d47c695884521a1719478f02769c666144` is awaiting its own CI result at the time of this note.
- No Neon writes, B2 writes, service creation, secret changes, deployment, or merge to `main` occurred in this code slice.

- Added `migrations/drafts/0001_factory_ledger.sql` and `docs/NEON_FACTORY_LEDGER_SCHEMA.md` as review-only schema artifacts. The draft includes append-only triggers (including TRUNCATE protection), idempotency keys, and composite task/attempt/artifact foreign keys. It has not been SQL-validated or executed; no Neon branch was created.
- CI run `43747315591` confirmed `23 passed in 0.04s` for the Python code slice. Later docs/schema commits are being checked by the same tests; no SQL integration test is configured.
