# Autonomous Software Factory — Master Execution Plan

**Document status:** Working baseline, version 0.1  
**Created:** 2026-11-15  
**Control repository:** `grinlife4-stack/TRADIX`  
**Branch:** `factory/phase-0-blueprint`  
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
- Backblaze B2: S3-compatible object-storage target; the user created a private bucket and supplied its endpoint/region. Adapter code is being added on the isolated factory branch; runtime credentials and live connectivity remain unverified.
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
| Neon | Connected; project `TRADIX NEON` identified | Seven memory-related tables were previously created only on a temporary branch; production schema and migration status must be re-inspected before use |
| Cloudflare | Connected; authenticated account identity verified | Not selected as the current object-storage target; keep the connector for other Cloudflare services |
| Backblaze B2 | User reports private bucket `tradix-factory-storage`, region `us-east-005`, encryption enabled; endpoint metadata supplied | S3 adapter and verification script added on the isolated branch; runtime secrets are not configured and live API access has not been tested |
| Railway | Connected; authenticated user and personal workspace verified | Workspace currently reports zero projects; no service or deployment exists |
| Sentry | Not connected | Defer until a runtime service exists |
| Model provider adapter | Not implemented | Select providers only after defining security, cost, and fallback requirements |

Never place credentials in this public repository. The repository is public.

## 6. Execution phases and task ledger

Statuses: `NOT_STARTED`, `IN_PROGRESS`, `BLOCKED`, `DONE`, `VERIFIED`.

### Phase 0 — Establish the control record
- [x] Create this master plan on an isolated Git branch.
- [ ] Open a pull request for review; do not merge automatically.
- [ ] Establish a durable task/event schema and an append-only execution ledger.
- [ ] Define task IDs, state transitions, evidence references, and approval records.

### Phase 1 — Verify infrastructure and boundaries
- [ ] Re-inspect GitHub repository settings, branch rules, and CI workflow.
- [ ] Inspect Neon production and temporary branch schemas separately; do not migrate production.
- [x] Select Backblaze B2 instead of Cloudflare R2; user-created private bucket and endpoint metadata recorded.
- [ ] Add the five B2 settings as encrypted GitHub Actions repository secrets and run the manual read-only then write/read-back verification workflow; do not place secrets in source files or chat.
- [ ] Inspect Railway workspace, billing/trial limits, regions, persistent storage, and deployment model.
- [ ] Decide whether Railway is acceptable for the first non-production runtime; compare alternatives before committing.
- [ ] Define secret storage and runtime-to-Neon/R2 connectivity without exposing secret values.
- [ ] Defer Sentry until the first service can emit telemetry.

### Phase 2 — Build the smallest vertical slice
- [ ] Select one tiny, reversible task in a non-production branch.
- [ ] Implement a task state machine: queued → planned → implementing → testing → review → candidate → deployed-test → verified; with blocked/failed/cancelled terminal handling.
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

1. Review and merge this plan through a pull request; do not merge without user approval.
2. Inspect the actual TRADIX repository files and workflow to establish the real baseline.
3. Review Railway workspace and pricing constraints; no project/service currently exists.
4. Configure B2 secrets in an approved runtime and run the documented connectivity test; this is blocked until a runtime is approved.
5. Inspect Neon production schema read-only and continue the first vertical-slice design.

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

## 10. Interoperability and communication standards

TRADIX follows the rule **USE ESTABLISHED STANDARDS ONLY**.

- Do not invent proprietary communication protocols, agent protocols, wire formats, or protocol dialects.
- Select a standard only when a concrete integration or communication requirement arises; do not add technologies speculatively.
- Choose the smallest suitable set of mature, documented, secure, interoperable standards, considering maintainability and operating cost.
- Evaluate A2A for agent-to-agent delegation/discovery and MCP for standardized access to tools, resources, and context when those use cases arise.
- Use established HTTP APIs or gRPC for service communication according to compatibility and performance needs.
- Consider MQTT or OPC UA only when actual industrial-device integration requires them.
- Use standard data formats and validation tools such as JSON and JSON Schema where suitable. Project-specific schemas are data contracts, not new communication protocols.
- Build adapters only to bridge existing standards, vendors, or legacy systems. An adapter must not turn into a proprietary protocol or a replacement for an established standard.
- Record the concrete requirement, chosen standard, alternatives, security implications, and selection rationale in the relevant project documentation.

This is a standing architectural principle, not a separate product or implementation project. Apply it at the point of need.

## 11. Best-of-breed and vendor-independent architecture

TRADIX follows **BEST-OF-BREED, VENDOR-INDEPENDENT ORCHESTRATION** as a foundational architecture rule.

- Select, combine, and orchestrate the best suitable existing software, models, services, and infrastructure. Rebuild mature capabilities only when a documented technical, security, cost, or control reason justifies it.
- Prefer free and open-source options when they meet the required quality, security, license, maintenance, and operational criteria. Evaluate total cost: source availability does not remove hosting, compute, API/model usage, storage, support, migration, or maintenance costs.
- No vendor, model, platform, database, storage provider, runtime, or tool may become an exclusive dependency or an unmitigated single point of failure.
- Keep TRADIX core policy, project state, credentials, audit history, and data contracts under TRADIX-controlled and portable boundaries.
- Integrate through documented, established interfaces. Isolate provider-specific behavior behind replaceable adapters; do not let an adapter become a proprietary protocol.
- Route each task by required capability and verified quality, not by vendor name. Maintain a capability/provider registry with versions, license and commercial-use constraints, health/access state, cost limits, security scope, portability, alternatives, limitations, and verification evidence.
- Design for health checks, bounded retries, graceful degradation, and controlled failover. Before switching providers, verify contract compatibility, state and data integrity, audit continuity, and least-privilege permissions.
- A replacement must not automatically inherit secrets, broader permissions, or access to other project namespaces. Existing human approval gates remain in force.
- For critical capabilities, maintain at least one viable tested alternative or a documented recovery path where practical. Verify replacements with contract tests and periodic replacement drills.
- If no safe compatible alternative exists, fail closed and report the exact dependency. Never claim provider independence merely because an adapter interface exists.

**Implementation status:** This change establishes the mandatory policy. Provider registry, adapters, automated routing/failover, portability checks, and replacement drills remain implementation work and must be reported as PLANNED until tested.
