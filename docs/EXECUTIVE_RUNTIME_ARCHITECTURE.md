# TRADIX Executive Runtime Architecture

**Status:** Architecture proposal v0.1 — review required  
**Repository:** `grinlife4-stack/TRADIX`  
**Branch:** `factory/executive-runtime-architecture-v0-1`  
**Purpose:** Define the smallest reliable foundation for one primary execution leader to use multiple AI models, tools, and execution environments without fragmenting project control.

## 1. Operating principle

The user defines the objective, constraints, and approval boundaries. The primary execution leader owns the end-to-end work: understanding the request, planning, performing available actions, verifying results, and reporting the actual outcome.

Other models, agents, applications, and cloud environments are capabilities the leader may use when they provide a concrete advantage. They do not become separate command centers and do not acquire authority merely because they are connected.

The factory must preserve task state and evidence independently of any model, chat session, or vendor.

## 2. Target operating model

- **User:** sets goals, priorities, constraints, and reserved approvals.
- **Primary execution leader:** the single operational point of contact and accountable coordinator. In the current build phase this role is performed through the ChatGPT session and its actually connected tools; it must not be represented as a continuously running autonomous process.
- **TRADIX runtime:** the future persistent system that stores tasks, state, ownership, events, artifacts, approvals, and execution outcomes.
- **Capability providers:** optional AI models, software tools, APIs, repositories, databases, and compute environments. The leader selects and uses them as needed.
- **Independent verification:** deterministic tests, policy checks, artifact integrity checks, and where useful a separate reviewer. The producer must not be the sole authority on correctness.

## 3. Minimal logical architecture

### A. Control core

1. **Task intake and contract** — converts a user objective into a bounded task with repository/project scope, acceptance criteria, risk class, and approval requirements.
2. **Execution coordinator** — maintains the plan, dependencies, current owner, attempt number, deadlines, and next action.
3. **Policy and approval gate** — enforces the user's authority boundaries before sensitive actions.
4. **Capability registry** — records which model/tool/runtime adapters exist, their verified permissions, limits, and health. A listed capability is not considered available until a real call succeeds.

### B. Capability adapters

1. **Model gateway** — provider-neutral interface for model requests and responses. Model output is untrusted data; it never becomes executable authority by itself.
2. **Tool gateway** — adapters for GitHub, databases, storage, monitoring, deployment systems, and other applications. Use the supported native connector/API/MCP/CLI path for each service.
3. **Execution sandbox** — isolated, bounded workspaces for code generation, builds, tests, and scripts. It must not inherit production credentials by default.
4. **Artifact interface** — stores immutable or versioned outputs with hashes, metadata, and provenance.

### C. Durable state and evidence

- **Task projection:** current operational view of each task.
- **Append-only event history:** who/what changed task state, when, and why.
- **Attempts and leases:** execution ownership, expiry, retry count, and fencing token.
- **Approvals:** explicit, immutable records for actions requiring user authorization.
- **Artifacts and evidence:** source snapshots, diffs, test reports, review reports, logs, and checksums.
- **Idempotency:** retries must not create duplicate side effects.

GitHub remains the source of truth for source code, commits, branches, pull requests, and CI evidence. The TRADIX runtime ledger is the source of truth for operational task state. A repository is a shared collaboration surface, not the factory's brain.

## 4. Continuity and automatic takeover

Automatic takeover is permitted for routine, already-authorized work. It must use this protocol:

1. The current worker holds a time-bounded lease for a specific task attempt.
2. Progress is checkpointed as durable events and artifacts.
3. A health monitor detects an expired lease or repeated lack of progress; a single missed heartbeat is not sufficient evidence of failure.
4. The coordinator marks the attempt abandoned or timed out and issues a new fencing token.
5. A replacement capability is selected using task fit, verified access, privacy, reliability, rate limits, and cost policy.
6. The replacement receives the task contract, last committed checkpoint, relevant artifacts, unresolved questions, and prior failure details.
7. The replacement verifies the checkpoint before continuing.
8. Stale workers cannot commit results after losing their lease.
9. The final output passes the same acceptance and verification gates as any other attempt.

A logical block, conflicting evidence, suspected data corruption, or an approval boundary is not treated as an ordinary provider outage. The system must stop safely or route the issue for the required approval.

## 5. Authority boundaries

The factory may autonomously perform actions that are explicitly within the task's approved scope, such as reading files, drafting code on an isolated branch, running bounded tests, and preparing a pull request.

The following remain approval-gated unless the user later defines a narrower explicit policy:
- production deployment;
- destructive or production database migrations;
- secret or credential changes;
- permission and access-control changes;
- irreversible external actions;
- new paid services, metered API usage, or increased spending limits;
- changing the user's objective or materially expanding task scope.

The factory must never infer approval from tool availability, an earlier unrelated approval, or a model's recommendation.

## 6. Interaction model

The user should have one primary interaction point. Internal coordination should not require the user to relay messages between models.

Models do not need direct vendor-to-vendor chat. They can collaborate through task-scoped, structured records and artifacts in the runtime. A provider may also be invoked directly through its API when appropriate. Shared tools such as GitHub can carry code and review artifacts, but must not be mistaken for a guaranteed real-time messaging bus.

## 7. Build sequence

### Stage 0 — Baseline and architecture
- Inventory existing code, workflows, branches, database schemas, and connected tools.
- Separate implemented behavior from proposals and fixtures.
- Approve this architecture and record unresolved decisions.

### Stage 1 — Durable task runtime
- Finalize task, attempt, event, approval, artifact, and evidence contracts.
- Implement transactional event append plus state projection and idempotency.
- Define roles, permissions, backup, restore, and integrity verification.
- Test on an isolated database branch only.

### Stage 2 — One primary executor
- Add one bounded worker that claims a task, reads scoped inputs, writes only to an isolated branch/workspace, runs tests, and produces evidence.
- Connect one model provider only after privacy, credentials, rate limits, and a hard spend ceiling are verified.
- Keep deployment disabled.

### Stage 3 — Recovery and capability substitution
- Add leases, heartbeats, checkpoints, fencing tokens, retry policy, and a second provider/tool adapter.
- Prove takeover using fault-injection tests, including a stale worker attempting to commit.

### Stage 4 — Independent verification
- Add deterministic policy/security checks and an independent review path.
- Require provenance and reproducible evidence for every candidate.

### Stage 5 — Product factory
- Demonstrate the complete workflow on a real but low-risk product using a category-appropriate production adapter. Software is one possible first category, not a limit on the factory's scope.
- Only after repeatable success, add more product categories through explicit production adapters, alongside tools, providers, project templates, and deployment targets.

## 8. Verified baseline at the time of this proposal

The following are present on the current TRADIX working branch:
- strict task-envelope validation and a finite evidence-gated state-transition contract;
- a provider-neutral model request/response interface and strict JSON plan parser;
- a deterministic demo that copies a reviewed fixture template, runs tests, performs static checks, and emits local evidence;
- GitHub Actions workflows for the demo and disposable PostgreSQL schema checks;
- a draft factory-ledger SQL schema and its documentation.

The following are not yet operational:
- a persistent orchestrator or task worker;
- a live model provider, provider credentials, or a verified model budget;
- a runtime model/tool gateway;
- a durable factory ledger in Neon;
- B2 artifact lifecycle, backup, and restore;
- automatic agent health monitoring, leases, takeover, and stale-worker fencing;
- independent semantic AI review;
- a deployed TRADIX runtime/API.

The successful fixture workflow proves only the bounded deterministic path described above. It does not prove autonomous AI software generation.

## 9. Non-goals and design constraints

- Do not build a separate microservice for every logical component before scale requires it.
- Do not connect every available provider or application in the first release.
- Do not make GitHub, a chat transcript, or a model's context window the sole operational memory.
- Do not let agents approve their own work or bypass task policy.
- Do not couple task contracts to one model vendor.
- Do not enable open-ended retries, unbounded parallelism, or unmetered API usage.
- Do not deploy or migrate production as part of the initial runtime build.

## 10. Acceptance test for operational independence

TRADIX is not considered operationally independent until it can, without user relay between tools:
1. accept a bounded task and persist its contract;
2. execute it in an isolated workspace;
3. preserve progress and evidence across process restart;
4. recover from a deliberately terminated worker;
5. transfer the task to a verified replacement without duplicate or stale writes;
6. pass independent acceptance checks;
7. produce a traceable candidate and concise report;
8. stop at any reserved approval boundary.

Passing a demo once is insufficient. The sequence must be repeatable under fault injection and recovery tests.


## 11. Conversational AI is the primary interface

The primary user interface is a replaceable conversational AI, not a human-operated administration panel. The user states goals and priorities in natural language. The interface AI translates them into project-scoped proposals, exchanges typed messages with the factory, resolves routine questions from durable context, and reports evidence-backed outcomes.

The interface AI is not the system of record and does not own approvals or execution authority. TRADIX owns durable state, policies, capability discovery, execution, artifacts, and evidence. The AI interface can be replaced without losing project continuity.

The bidirectional protocol is specified in `docs/AI_INTERFACE_ARCHITECTURE.md`, `schemas/ai-interface-message-v1.schema.json`, and `src/tradix/factory/interface_contract.py`. Factory needs are structured records with category, reason, priority, blocking status, and optional mission reference. The interface should resolve them from existing records and verified capabilities before asking the user.

Routine, reversible work within a standing project/resource policy should not require repeated approval. Reserved boundaries remain production changes, destructive operations, sensitive access, irreversible external effects, out-of-policy spending, and material scope changes. Model output is untrusted input and cannot approve itself or change policy.

This section defines the target architecture. The current branch contains validated protocol contracts and tests only; no conversational gateway, live model provider, durable message queue, or autonomous dispatcher is deployed.
