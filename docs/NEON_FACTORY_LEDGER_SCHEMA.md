# Neon Factory Ledger — Schema Draft

**Status:** Draft only. Not executed. Not approved for Production.  
**Target for eventual test:** A newly created isolated Neon branch.  
**Purpose:** Define operational records for the TRADIX factory without reusing the existing project-memory tables.

## Design decisions

- The `factory` schema is separate from `public` and from the seven existing `memory_*` tables.
- `task_events` is the append-only audit stream. Mutable task and attempt rows are projections/current operational state, not the only audit record.
- Approval decisions, evidence records, and artifact metadata are immutable rows. Corrections are represented by new events/records, not rewriting history.
- Each event has a unique idempotency key so a retry can be deduplicated.
- `factory.transition_task(...)` locks the task row, validates the lifecycle edge, checks required evidence/approval, appends the event, and updates the task projection in one transaction. Exact retries return the original event sequence; reuse of a key for different intent is rejected.
- Composite foreign keys prevent an attempt or artifact from being attached to a different task; evidence is bound to the exact producing attempt.
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

PostgreSQL triggers and grants reduce accidental mutation, but a database owner or superuser can alter/disable them. Production-grade immutability therefore also requires strict role separation, restricted migration ownership, backups, and independent integrity verification. This draft still does not define the application roles, RLS policy, connection pooler settings, or least-privilege grants. The transition function provides the atomic event-plus-projection transaction, but callers with direct UPDATE privilege on `factory.tasks` could bypass it. Before runtime use, define a non-owner application role, revoke direct status/projection writes from it, grant only the required function execution and scoped reads, and test the boundary using that role. The function is not a substitute for database privilege design. The SQL is not approved for Neon execution. A separate GitHub Actions job applies it only to a disposable PostgreSQL service and runs negative constraint/immutability tests; that job does not touch Neon.

## Required review before execution

1. Confirm the project namespace and whether one project may have multiple repositories.
2. Define who may create tasks, append events, decide approvals, and read artifacts.
3. Define RLS or a service-role boundary before exposing any endpoint.
4. Review the implemented transition function and add role-based negative tests proving the runtime role cannot bypass it with direct UPDATE, cannot mutate immutable records, and cannot cross project boundaries.
5. Add migration versioning and restore verification.
6. Validate SQL syntax, then test the migration on a new isolated Neon branch, including negative tests for UPDATE/DELETE/TRUNCATE on immutable tables and cross-task foreign-key violations.
7. Confirm Neon plan/branch costs before creating the test branch.

## Execution boundary

This SQL file is a review artifact only. It has not been run against Neon. No branch was created, no schema was applied, and Production was not modified.


## Runtime privilege boundary (draft, CI-only)

The draft ledger now provisions two isolated `NOLOGIN` roles. `factory_runtime` receives schema usage, SELECT on ledger tables, and EXECUTE only on `factory.transition_task(...)`; it receives no direct INSERT/UPDATE/DELETE/TRUNCATE privileges or sequence privileges. `factory_executor_owner` owns only the transition function and receives only the SELECT/INSERT/UPDATE table privileges its function body needs. It is not a superuser, does not own the ledger tables, has no login, and is not a member of the runtime role. The transition function is `SECURITY DEFINER` with a fixed safe search path; PUBLIC execution is revoked. The function rejects `actor_type='human'` so an application caller cannot label its own transition as a human action.

A deployment-specific login role must be provisioned separately and granted membership in `factory_runtime`. Do not grant the runtime login role ownership, superuser, CREATEROLE, schema CREATE, or direct table-write privileges. The migration owner remains the function owner and is a privileged administrative identity, not an application credential.

The integration test uses PostgreSQL role switching to prove that the runtime role can read and invoke the controlled transition while direct projection writes, event inserts, immutable-event updates, and TRUNCATE are denied. It also verifies that the function owner is NOLOGIN/non-superuser, is not a member of the runtime role, and that the runtime cannot spoof a human actor. This is draft SQL tested only in disposable PostgreSQL; it is not approved for Neon or Production. Review managed-role provisioning and default-privilege behavior before any migration.


## Neon role-provisioning compatibility review

The current Neon project exposes the PostgreSQL role `neondb_owner` with
`CREATEROLE` and without superuser status. Neon supports SQL role management,
so creating the two `NOLOGIN` roles in this draft does not inherently require
a separate Neon API provisioning step. The migration identity must have both
`CREATEROLE` and database `CREATE` privilege. This was inspected read-only
on the existing prototype branch; no role or schema was created there.

Important PostgreSQL 16+ behavior: when a non-superuser `CREATEROLE` role
creates another role, the automatic creator membership has `ADMIN TRUE`,
but `SET FALSE` and `INHERIT FALSE`. PostgreSQL requires the current
migration identity to be able to `SET ROLE` to the new owner before
`ALTER FUNCTION ... OWNER TO` succeeds. The draft therefore explicitly
grants `factory_executor_owner` back to `CURRENT_USER` with `SET TRUE`
and `INHERIT FALSE`. This does not grant the application runtime membership
in the function-owner role.

The CI migration is now applied by a non-superuser `tradix_migrator` with
`CREATEROLE` and database `CREATE`, rather than PostgreSQL's superuser.
Assertions verify the migration role can SET (but does not inherit) the
function-owner role, while `factory_runtime` cannot become a member of it.

This is still not proof of a Neon migration: no SQL was executed on any Neon
branch. Before a future isolated Neon-branch migration, verify the actual
migration connection identity and privileges, then inspect the resulting role
membership, function owner, function ACL, and default privileges. Production
remains out of scope.
