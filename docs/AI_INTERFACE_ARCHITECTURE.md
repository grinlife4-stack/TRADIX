# TRADIX Conversational AI Interface Architecture

**Status:** Proposed interface contract v1.0; implementation foundation only  
**Scope:** Conversational interface between the user, a replaceable interface AI, and the TRADIX factory runtime  
**Branch:** `factory/executive-runtime-architecture-v0-1`

## 1. Decision

The primary user interface is a conversational AI, not a human-operated administration panel. The user communicates goals and priorities in natural language. The interface AI translates intent into validated, project-scoped proposals, exchanges structured messages with TRADIX, interprets factory needs, and reports verified outcomes in human language.

TRADIX remains the authority for durable state, policy, capability inventory, execution, evidence, and product records. The interface AI is a replaceable interpreter and coordinator, not the factory's brain or source of truth.

## 2. Responsibilities

### User
- Defines outcomes, priorities, business intent, and high-level constraints.
- Answers only questions that cannot be resolved from authorized project records or available capabilities.
- Sets standing authority and resource limits through explicit policy changes.
- Receives concise reports of outcomes, risks, and decisions that genuinely require owner authority.

### Conversational interface AI
- Understands natural-language requests and resolves references using authorized project context.
- Identifies the target product/project; never silently crosses project boundaries.
- Converts intent into a mission proposal, status query, or capability query.
- Checks existing product dossiers, verified reusable assets, prior decisions, and evidence before asking the user or proposing new work.
- Sends structured, correlated messages to TRADIX.
- Interprets factory needs, resolves them from existing records/tools when possible, and asks the user only when genuinely necessary.
- Explains alternatives and trade-offs; reports only outcomes supported by factory records and evidence.
- Can be replaced by another model/provider without changing factory state or contracts.

### TRADIX factory runtime
- Validates message identity, project scope, schemas, policies, and idempotency.
- Owns mission/task state, capability registry, reusable asset catalog, event history, artifacts, and evidence.
- Determines what can proceed under standing policy.
- Executes work through bounded capability adapters and workers.
- Emits structured needs, status, blockers, and evidence-backed results.
- Continues work without requiring the interface model to retain the conversation or remain continuously connected.

## 3. Bidirectional protocol

All messages use `schemas/ai-interface-message-v1.schema.json` and the Python contract in `src/tradix/factory/interface_contract.py`.

Every message has:
- `message_id`: unique message identity;
- `conversation_id`: conversational thread identity, not the durable project identity;
- `project_key`: explicit product scope;
- `correlation_id`: mission or request correlation;
- `sender` and `message_type`: role-constrained message semantics;
- `body`: typed payload;
- `created_at` and optional `reply_to`.

Supported message directions:

| Sender | Message types | Purpose |
|---|---|---|
| User | `user_input` | Natural-language intent, supplied through an authenticated interface |
| Interface AI | `mission_proposal` | Bounded mission intent for validation and intake |
| Interface AI | `status_query` | Ask for durable mission/project status |
| Interface AI | `capability_query` | Ask which verified tools/assets are available |
| Interface AI | `clarification_answer` | Return a grounded answer to a factory need |
| Factory | `factory_need` | Ask for missing information, a capability/resource, policy decision, reserved approval, or dependency resolution |
| Factory | `status_update`, `result`, `blocked` | Report progress, evidence-backed completion, or a blocker |

The factory need contract distinguishes the question from its reason, priority, and whether progress is blocked. A factory need is not an approval and cannot grant itself authority.

## 4. Authority and trust model

1. Model output is untrusted input. It is parsed and validated; it is never executable authority merely because a model produced it.
2. The interface AI may propose missions and relay answers. It cannot approve its own proposal, change standing policy, widen project scope, grant permissions, or mark a task complete.
3. User approval is recorded only through a separately authenticated approval path and bound to the exact action/intake/version. A conversational paraphrase or inferred intent is not an approval record.
4. The factory, not the interface AI, evaluates the standing execution policy and decides whether a routine action is already authorized.
5. Ordinary reversible work inside an explicitly configured project/resource policy should not require a fresh human approval for every task. High/critical risk, out-of-policy spending, production changes, sensitive access, irreversible external effects, and material scope changes remain reserved boundaries unless the owner explicitly configures a narrower policy.
6. If the factory cannot prove identity, scope, policy, state, or evidence, it fails closed and emits a structured need/blocker instead of guessing.

This document does not itself authorize any new spending, deployment, database migration, permission change, or external side effect.

## 5. Conversation is not the system of record

Conversation transcripts are ephemeral transport and user experience. They are not authoritative memory.

The factory must persist:
- mission and task contracts and versions;
- decisions, policy versions, and approval records;
- messages needed for audit/correlation (with retention and privacy controls);
- execution events, attempts, checkpoints, and leases;
- reusable assets, dependency metadata, and verification evidence;
- factory needs and their resolution status.

A new model or chat session must be able to resume by querying the factory's durable project state, not by reconstructing the project from old chat history.

## 6. Interaction loop

1. User states an outcome naturally.
2. Interface AI identifies project scope and retrieves relevant durable context and reusable assets.
3. Interface AI creates a bounded mission proposal and acceptance criteria; it asks a question only if a material ambiguity cannot be resolved safely.
4. TRADIX validates and records the proposal through the existing product-intake boundary.
5. The factory evaluates policy. When execution orchestration is implemented, it starts all work already authorized by standing policy without asking for repeated approval.
6. During work, the factory emits structured needs/status. The interface AI resolves needs from context/capabilities first and escalates only genuine owner decisions.
7. Workers execute, test, repair, and independently verify the result.
8. TRADIX records artifacts and evidence and emits a result. The interface AI translates the verified result into a concise report.

## 7. Reusable capability discovery

Before proposing new work, the interface asks the factory capability/asset registry for:
- existing verified modules and blueprints;
- compatible product templates;
- tested adapters and available tools;
- project-specific constraints and decisions;
- prior failed approaches and known limitations.

Reuse requires compatibility checks: version, dependency constraints, license, security classification, project isolation, and current verification status. Copying unverified code is not reuse; it is importing an unknown defect.

## 8. Failure and continuity

- The interface AI may disconnect, change vendor, or lose conversation context without losing factory state.
- The factory can emit a need and wait durably while the interface is unavailable.
- Another authorized interface AI can retrieve the open needs and resume the conversation.
- Duplicate messages are idempotent by message/request identity.
- Stale or out-of-scope responses are rejected by correlation and project checks.
- A model timeout is not a factory task failure; execution state belongs to the runtime.

## 9. Implementation status and explicit gaps

Implemented in this change:
- provider-neutral Python message and factory-need contracts;
- sender/type restrictions and project/identifier validation;
- JSON Schema for the versioned message protocol;
- unit tests for invalid sender combinations, malformed needs, scope errors, and invalid payloads;
- architecture and authority-boundary documentation.

Not implemented yet:
- a deployed conversational gateway or chat UI;
- a live model-provider connection;
- persistent message inbox/outbox and delivery/retry worker;
- runtime capability registry API;
- durable factory-need table and resolution workflow;
- end-to-end autonomous dispatch/execution and automatic owner notification.

The current `POST /v1/intake` records a proposed dossier, mission, and task plan and stops at its existing pending-approval boundary. This interface contract does not bypass that boundary. No model provider, credentials, paid API, Neon migration, production write, deployment, or merge is included.

## 10. Acceptance criteria for the next vertical slice

A first runnable conversational vertical slice is complete only when tests prove:
1. a user goal can be normalized into a project-scoped proposal;
2. the proposal is persisted idempotently;
3. the factory can return a structured need correlated to the proposal;
4. the interface can resolve a need from stored context or ask the user;
5. a different interface model/session can resume from durable state;
6. the interface cannot forge user identity, approvals, project scope, or execution results;
7. a factory result is reported only after independent evidence checks.
