# ECOSCAN Security Status

**Status:** Phase 1 foundation only; not approved for production scans.

Implemented:
- Strict project-registry parsing, exact field sets, unique source IDs, timezone-aware timestamps, and bounded scan budgets.
- Default-deny global/project/subsystem/source controls.
- Owner/operator authorization callback; missing authorization denies.
- Per-project SQLite files and append-only measurement/coverage APIs.
- Checkpoint persistence isolated within each project's database.
- No network adapter, credential resolver, filesystem scanner, or arbitrary command execution.

Not yet implemented or proven:
- Secure local filesystem traversal, race-resistant symlink handling, mount-boundary enforcement, and resumable scan execution.
- Adapter invocation runner and revalidation of controls before each bounded operation.
- Export/import, manifest verification, safe archive extraction, and portability round-trip.
- Credential-reference resolution and real owner/operator identity integration.
- Tamper-evident audit history, encryption at rest, backup/restore, and migration.
- Any live GitHub, Backblaze B2, host, or monitoring integration.

Until those gaps are closed and reviewed, do not use this package to scan production project data. The current CLI only validates a registry and initializes a project-local database.
