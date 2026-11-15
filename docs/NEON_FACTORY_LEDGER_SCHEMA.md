# Neon Factory Ledger — Schema Draft

**Status:** Draft only. Not executed. Not approved for Production.  
**Target for eventual test:** A newly created isolated Neon branch.  
**Purpose:** Define operational records for the TRADIX factory without reusing the existing project-memory tables.

## Design decisions

- The `factory` schema is separate from `public` and from the seven existing `memory_*` tables.
- `task_events` is the append-only audit stream. Mutable task and attempt rows are projections/current operational state, not the only audit record.
- Approval decisions, evidence records, and artifact metadata are immutable rows. Corrections are represented by new events/records, not rewriting history.
- Each event has a unique idempotency key so a retry can be deduplicated.
- Composite foreign keys prevent an attempt or artifact from being attached to a different task.
- Append-only triggers reject UPDATE, DELETE, and TRUNCATE on events, approvals, evidence, and artifact metadata.
- Every task belongs to an explicit project namespace and repository.
- High and critical risk tasks cannot exist without an approval requirement.
- Foreign keys use `ON DELETE RESTRICT`; this design does not provide cascade deletion.
- No public API, model key, or service credential is stored in this schema.

## Tables

| Table | Purpose |
|---|---|
| `projects` | Isolated project registry |
| `tasks` | Current task projection and validated scope |
| `task_attempts` | Bounded execution attempts and worker roles |
| `task_events` | Append-only lifecycle and audit events |
| `task_approvals` | Immutable human approval decisions |
| `task_artifacts` | Immutable artifact URI, SHA-256, size and type |
| `task_evidence` | Evidence records tied to stored artifacts |

## Critical limitation

PostgreSQL triggers and grants reduce accidental mutation, but a database owner or superuser can alter/disable them. Production-grade immutability therefore also requires strict role separation, restricted migration ownership, backups, and independent integrity verification. This draft does not yet define the application roles, RLS policy, connection pooler settings, or transaction protocol that writes an event and updates its projection atomically. The SQL has not been parsed or executed against PostgreSQL yet; CI currently tests Python only.

## Required review before execution

1. Confirm the project namespace and whether one project may have multiple repositories.
2. Define who may create tasks, append events, decide approvals, and read artifacts.
3. Define RLS or a service-role boundary before exposing any endpoint.
4. Define the transaction contract: append event + update projection + store idempotency outcome atomically.
5. Add migration versioning and restore verification.
6. Validate SQL syntax, then test the migration on a new isolated Neon branch, including negative tests for UPDATE/DELETE/TRUNCATE on immutable tables and cross-task foreign-key violations.
7. Confirm Neon plan/branch costs before creating the test branch.

## Execution boundary

This SQL file is a review artifact only. It has not been run against Neon. No branch was created, no schema was applied, and Production was not modified.
