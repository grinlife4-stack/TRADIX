# ECOSCAN

ECOSCAN is an optional, independent, read-only inventory tool for the wider project ecosystem. It can be run against the whole registry, one project, or one registered source. The system, each project, and each source have independent enable/disable switches.

## Phase 1: local-only runtime

**The default entry point is offline and local-only.** It uses only the Python standard library and does not initialize or call GitHub, Railway, Backblaze, S3, a database service, or any other network provider.

The local scanner reads filesystem metadata only. It does not open or copy source-file contents, modify source files, follow symbolic links, or execute source code. Missing or inaccessible sources are reported as PARTIAL, never as zero usage.

Run from the repository root with Python 3.11 or newer:

```bash
python -m tools.ecoscan
```

The default demonstration registry points only to synthetic fixtures under tests/fixtures/ecoscan/sample_project. Replace or extend the registry for real local paths only after reviewing the paths and access scope.

```bash
# Entire local registry
python -m tools.ecoscan --scope ecosystem

# One project
python -m tools.ecoscan --scope project --project ECOSCAN_DEMO

# One source
python -m tools.ecoscan --scope source --source ecoscan-demo-files

# Choose explicit local state and export directories
python -m tools.ecoscan --database-dir .ecoscan/db --output-dir .ecoscan/exports --format both
```

Registry: tools/ecoscan/config/local-registry.json.

Each project receives its own SQLite database file, for example ALPHA.sqlite3. Measurements are append-only by unique scan ID. JSON and JSONL exports include a versioned manifest and can be imported into another local database:

```bash
python -m tools.ecoscan --config tools/ecoscan/config/local-registry.json --import .ecoscan/exports/ECOSCAN_DEMO.jsonl --import-project ECOSCAN_DEMO --database-dir /path/to/other/db
```

## Registry controls

- system_enabled: false disables scanning before database or export directories are created.
- projects[].enabled: false disables all sources in that project.
- projects[].sources[].enabled: false disables only that source.
- Phase 1 accepts only provider: filesystem_local. Any other provider is rejected during registry validation.
- Relative source paths are resolved relative to the registry file. Database and export directories are resolved relative to the process working directory.

Example source entry:

```json
{
  "source_id": "project-local-files",
  "provider": "filesystem_local",
  "path": "/local/path/to/project",
  "enabled": true
}
```

## Data and safety boundaries

- One SQLite file per project keeps project histories independently exportable and transferable.
- Exports are portable JSON/JSONL; import validates project ownership, schema version, record counts, IDs, statuses, and non-negative sizes. Re-import is idempotent.
- The scanner records aggregate file count and byte count, not file contents or full absolute paths.
- Symbolic links are skipped; a source root containing a symbolic-link path component is rejected.
- The runtime has no network-client, subprocess, cloud SDK, or external database imports.
- The previous provider-oriented monitor implementation is not imported by the default entry point. Provider integrations remain outside Phase 1 and must not be enabled as part of local acceptance.

## Phase 1 acceptance boundary

Phase 1 is accepted only after the local test suite passes, the CLI completes a fixture scan, per-project SQLite separation is verified, JSON/JSONL export-import round trips pass, and the default entry point is proven not to import the legacy provider monitor.

GitHub, Backblaze B2, R2, S3, Railway, scheduled jobs, cloud backups, and remote reporting are explicitly deferred. No cloud credentials or services are required for this phase.
