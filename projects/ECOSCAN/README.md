# ECOSCAN

ECOSCAN is an independent project-level inventory system. Its runtime, source registry, project stores, controls, exports, and lifecycle are separate from TRADIX. The package has no TRADIX runtime imports and uses only the Python standard library at runtime.

## Phase 1: local-only

Phase 1 supports local filesystem metadata inventory only. It does not read file contents, modify source files, execute files, follow symbolic links, or initialize network clients. GitHub, Backblaze, S3/R2, Railway, external databases, scheduled scans, remote reporting, and cloud backups are deferred.

Install from this project directory:

```bash
python -m pip install -e ".[test]"
```

Validate the sample ecosystem registry:

```bash
python -m ecoscan validate-registry config/ecosystem-registry.json
```

Run the synthetic demo. The controls file explicitly enables only the synthetic ECOSCAN_DEMO project, storage subsystem, demo-files source, and demo operator:

```bash
python -m ecoscan scan --registry config/ecosystem-registry.json --controls config/controls.example.json --actor demo-operator --scope ecosystem --db-dir .ecoscan/db --export-dir .ecoscan/exports --format both
```

The scan creates one SQLite file per project. JSON and JSONL exports include a versioned manifest and can be imported into another local store:

```bash
python -m ecoscan import --project ECOSCAN_DEMO --db-dir /path/to/new-db --file .ecoscan/exports/ECOSCAN_DEMO.jsonl
```

## Scope and controls

- Global switch: global_enabled.
- Project switch: membership in enabled_projects.
- Section/subsystem switch: (project_id, subsystem_id) in enabled_subsystems.
- Source switch: (project_id, source_id) in enabled_sources and source enabled: true.
- Owner/operator authorization is separate from switches and must match an explicit five-part tuple in authorized_actors. Missing, false, exceptional, or non-boolean authorization fails closed.
- ecosystem, project, section, and source scopes are supported. Section means a registered subsystem, not arbitrary path traversal.

## Storage and transfer

Every project has its own append-only SQLite database. Coverage, measurements, and checkpoints are committed atomically. Duplicate scan/measurement IDs are rejected on normal append. Import is idempotent and validates manifest version, project ownership, counts, and scan references.

The local filesystem adapter records logical bytes and file count from lstat metadata. It never opens source contents. Symbolic links are skipped and recorded as coverage limitations. Missing or inaccessible roots fail the scan rather than being reported as zero usage.

## Independence proof

The package can be installed and tested from this directory without installing TRADIX. Its runtime modules contain no network clients, subprocess launchers, cloud SDKs, or imports from TRADIX. All Phase 1 tests run offline against synthetic fixtures.
