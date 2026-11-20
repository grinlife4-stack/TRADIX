# ECOSCAN

ECOSCAN is an independent project-level inventory system. Its runtime, source registry, project stores, controls, exports, and lifecycle are separate from TRADIX. The package has no TRADIX runtime imports and uses only the Python standard library at runtime.

## Phase 1: local-only

Phase 1 CLI supports local filesystem metadata inventory only. It does not read file contents, modify source files, execute files, follow symbolic links, or initialize network clients. The package also includes an opt-in OBIS adapter contract that accepts an externally injected authenticated client; the CLI does not register or invoke it. GitHub, Backblaze, S3/R2, Railway, external databases, scheduled scans, remote reporting, and cloud backups remain deferred.

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

## Future Bridge connection

The external integration path is deliberately preserved as a separate, independently deployable ECOSCAN Bridge using OBIS. Provider-specific clients and credentials must live in that Bridge, not in the ECOSCAN core. ECOSCAN accepts only bounded, typed, project/source-authorized inventory records through its own validation boundary.

The ECOSCAN OBIS adapter now exists and is covered by synthetic peer tests. It accepts an injected OBIS client, calls the versioned read-only capability `ecoscan.inventory.read`, and checks peer identity, recipient identity, project/source binding, measurement kinds, and local page/item budgets. The Bridge owns provider credentials; ECOSCAN receives only an external credential reference and never loads the secret itself. The CLI intentionally does not register this adapter, and no remote peer or endpoint is configured. The current BRIDEX OBIS reference client/server is loopback-only and development-only, not production-ready. The matching Bridge-side `ecoscan.inventory.read@1.0` capability and per-credential project/source grant are being added in TRADIX PR #66. The connection is staged: local acceptance first; loopback OBIS conformance second; production transport/security review third; then an explicitly approved read-only provider pilot.

See [ECOSCAN Bridge Integration Plan](docs/ECOSCAN_BRIDGE_INTEGRATION_PLAN.md) for the topology, implemented adapter contract, capability payload, trust boundaries, staged gates, and independence tests.
