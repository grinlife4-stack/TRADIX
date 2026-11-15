# First Vertical Slice — Contract and Execution Boundary

**Status:** Implementation contract for the first provider-free code slice  
**Repository:** `grinlife4-stack/TRADIX`  
**Scope:** Task-envelope validation and evidence-gated state transitions only

## Objective

Establish a small, testable foundation for the factory without pretending that an autonomous agent runtime already exists. This slice has no network access, database writes, model calls, branch creation, object-storage writes, or deployment.

## Included

- Strict task input contract with required fields, bounded text, project namespace, repository identifier, risk class, and approval flag.
- Unknown fields rejected by default.
- High and critical risk tasks cannot be accepted without an explicit human-approval requirement.
- Explicit lifecycle graph with terminal states.
- Evidence required before testing can pass to review, review can pass to candidate, and test deployment can pass to verified.
- Pure functions so behavior is deterministic and can be tested in GitHub Actions.

## Excluded

- LLM planning or code generation.
- GitHub API execution from the runtime.
- Neon persistence or reuse of the existing `memory_*` tables.
- B2 artifact upload or backup/restore.
- Railway services, public API endpoints, webhooks, and scheduled workers.
- Production deployment, migrations, permission changes, and secret management.

## Why the temporary Neon tables are not reused yet

The temporary Neon branch contains seven tables named `memory_projects`, `memory_events`, `memory_work_items`, `memory_artifacts`, `memory_conversations`, `memory_decisions`, and `memory_project_aliases`. Their columns and constraints were inspected. They model project memory and work-item context, but they do not establish the complete factory execution ledger, approval lifecycle, or immutable evidence chain. In particular, the schema inspection did not demonstrate append-only enforcement for `memory_events`. No data was written and Production was not touched.

A separate factory schema must be designed and reviewed before any migration. It should cover tasks, attempts, events, approvals, artifacts, evidence, and idempotency, with append-only protections and explicit ownership boundaries.

## Acceptance criteria for this slice

1. Valid bounded task envelopes parse deterministically.
2. Missing, unknown, malformed, or over-limit fields fail closed.
3. High and critical risk require human approval.
4. Illegal lifecycle transitions are rejected.
5. Evidence gates reject missing evidence and accept a non-empty evidence reference.
6. The full existing test suite and new tests pass in GitHub Actions.
7. No external service, secret, database, or deployment is used.

## Next slice after CI passes

Design a factory-specific Neon schema in a migration file only. Review it read-only, then apply it only to a newly isolated Neon branch after explicit approval. Do not migrate Production.
