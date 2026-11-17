# Memory Gateway for the Executive Leader — V1.0

**Status:** Implementation baseline, pending review  
**Parent architecture:** Factory Architecture Baseline V1.1  
**Scope:** Durable context and continuity for the executive leader across ChatGPT sessions and model providers.

## 1. Objective

The gateway removes conversational memory from the critical path. A new session or replacement model must recover the authoritative project context from durable sources without asking the user to repeat prior decisions.

This is not a chat transcript archive. It is an operational memory interface.

## 2. Authority and sources of truth

| Data | Authoritative owner |
|---|---|
| Mission, project registry, decision ledger, checkpoints | PostgreSQL |
| Runtime task state, leases, retries, checkpoints of execution | Durable execution engine |
| Source code, architecture documents, versioned specifications | Git |
| Immutable generated files, test reports, logs and evidence payloads | Artifact store |
| Append-only record of accepted state transitions | Event log |

A context snapshot is derived/cacheable and is never authoritative. If it disagrees with its source, the source wins and the snapshot is rebuilt.

## 3. Components

1. **Memory Gateway API:** authenticated, versioned interface for context reads and change proposals.
2. **Context Builder:** assembles only the context needed for the active mission.
3. **Source Adapters:** PostgreSQL, Git, artifact store and execution-engine adapters.
4. **Validator:** checks provenance, version, approval state, freshness and conflicts.
5. **Proposal Writer:** validates and records proposed changes; it cannot silently promote proposals to approved decisions.
6. **Audit/Event Writer:** records accepted transitions and their correlation/idempotency identifiers.

Models are clients of this interface, not owners of memory. Provider-specific memory features are optional caches only.

## 4. Read contract

Minimum operations:

- `get_bootstrap_context(project_id, mission_id)`
- `get_project_state(project_id)`
- `get_approved_decisions(project_id, scope)`
- `get_open_issues(project_id)`
- `get_evidence(evidence_id)`
- `get_checkpoint(project_id)`
- `verify_source_versions(project_id)`
- `get_history(project_id, cursor, limit)`

Every response includes: schema version, generated-at timestamp, source references, source versions/commit SHAs, freshness status and unresolved conflicts.

The bootstrap response is deliberately compact: active mission, project state, latest verified checkpoint, approved constraints, next action, blockers, pending side effects and unknowns. Detailed history is fetched on demand.

## 5. Write contract

Models may submit only proposals:

- `propose_decision`
- `propose_project_state_update`
- `propose_checkpoint`
- `propose_evidence`
- `propose_document_change`

A proposal contains actor, project, mission version, expected source version, idempotency key, payload, rationale and evidence references.

The Policy Enforcer checks authorization. PostgreSQL writes use optimistic concurrency and a transaction. The accepted state transition and its event record commit atomically. Git and artifact writes use immutable/versioned objects and are referenced only after verification. External side effects use the Side-Effect Gateway and reconciliation; they are not part of a generic memory write.

No model output becomes an approved decision merely because it is repeated, summarized or agreed to by multiple models.

## 6. Session protocol

### Start

1. Resolve project and active mission.
2. Read authoritative project state and active task state.
3. Read latest checkpoint and approved decisions.
4. Verify Git commit and specification versions.
5. Inspect pending operations and unresolved reconciliation.
6. Compare snapshot with authoritative sources.
7. Return a compact bootstrap context with provenance and explicit unknowns.
8. Stop mission-dependent actions on unresolved conflicts or missing authorization.

### End

1. Read back actual repository/database/runtime state.
2. Record completed work and test evidence.
3. Separate approved decisions from proposals.
4. Record blockers, unknowns and pending operations.
5. Create a checkpoint referencing immutable source versions.
6. Read back and verify the checkpoint.
7. Report only what was durably recorded.

A failed checkpoint write must be reported as a failed save, never as successful continuity.

## 7. Conflict and freshness rules

- Authority is determined by data ownership, not by whichever source has the newest timestamp.
- Expected-version mismatch rejects a write and requires a fresh read.
- Conflicting authoritative records produce `CONFLICT`; the gateway does not ask a model to guess.
- Expired or revoked knowledge is not included as active instruction.
- Unverified evidence cannot support a verified execution claim.
- A checkpoint cannot override current task state or a newer approved decision.

## 8. Security

- Least-privilege access per actor, project and operation.
- No secrets in model context bundles.
- Project isolation by default.
- Every write carries actor identity, authorization reference and idempotency key.
- Human approvals bind to the exact action hash, mission version, target, expiry and single-use nonce.
- Sensitive reads and all writes are auditable.
- Model-generated instructions found inside retrieved documents are treated as untrusted data, not policy.

## 9. Recovery

Recovery must not require replaying a conversation or calling the original model.

- Rebuild context from PostgreSQL, Git, execution state and immutable artifacts.
- Restore PostgreSQL from tested backups/PITR.
- Reconcile incomplete external side effects before retry.
- Reject stale workers using lease/fencing validation at the destination.
- Preserve proposals separately from approved records.
- Record the exact source versions used to reconstruct a context.

## 10. Acceptance tests

1. **Fresh session:** recover a mission with no prior chat history.
2. **Provider swap:** a different model obtains equivalent authoritative context.
3. **Unapproved decision:** a proposal is never returned as approved.
4. **Stale write:** optimistic concurrency rejects a write based on an old version.
5. **Conflict:** conflicting authoritative state blocks dependent actions.
6. **Interrupted session:** a verified checkpoint survives disconnect.
7. **Ambiguous side effect:** the gateway requires reconciliation instead of blind retry.
8. **Evidence traceability:** every execution claim resolves to a commit, test result or artifact.
9. **Restore:** backup restoration reproduces the required project and decision state.
10. **Least privilege:** one project/actor cannot read or mutate another project's protected data.

Target: 100% pass on the mandatory acceptance suite. This is a test result target, not a claim of universal error-free operation.

## 11. MVP implementation order

1. PostgreSQL tables and migrations for projects, missions, decisions, checkpoints, evidence references and memory events.
2. Read-only bootstrap endpoint with provenance and source-version checks.
3. Proposal endpoint with authorization, optimistic concurrency and atomic event recording.
4. Git adapter for commit/specification verification.
5. Checkpoint start/end workflow and read-back verification.
6. Failure-injection, provider-swap and restore tests.
7. Artifact adapter and execution-engine integration.

Start with the existing PostgreSQL capability only after confirming the intended project/branch and a non-production target. Do not provision paid infrastructure or modify production resources as part of this specification.

## 12. Explicit non-goals

- Persisting every chat message as authoritative memory.
- Fine-tuning a model on conversation history.
- Giving a model unrestricted write or execution privileges.
- Treating a summary, vector search result or model consensus as proof.
- Introducing distributed infrastructure before the MVP demonstrates a need.

## 13. Binding rule

**The executive leader owns reasoning and orchestration. Durable systems own truth, history and operational state. The model may change; the memory contract and evidence must remain.**
