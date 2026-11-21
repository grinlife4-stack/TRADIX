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

Every project has its own append-only SQLite database. Coverage, measurements, and checkpoints are committed atomically. Durable OBIS operation intents and status-reconciliation events are stored separately; a recovered result never overwrites the original INDETERMINATE coverage record. Status reconciliation performs a read-only operation-status query and never resubmits the provider operation. Operation intents and reconciliation evidence are included in JSON/JSONL export and idempotent import. Import validates manifest version, project ownership, counts, and record references.

The local filesystem adapter records logical bytes and file count from lstat metadata. It never opens source contents. Symbolic links are skipped and recorded as coverage limitations. Missing or inaccessible roots fail the scan rather than being reported as zero usage.

## Independence proof

The package can be installed and tested from this directory without installing TRADIX. Its runtime modules contain no network clients, subprocess launchers, cloud SDKs, or imports from TRADIX. All Phase 1 tests run offline against synthetic fixtures.

## Future Bridge connection

The optional external integration path uses a separately deployable Bridge owned by the project whose external source/resources it exposes, communicating with ECOSCAN through OBIS. Provider-specific clients and credentials must live in that Bridge, not in the ECOSCAN core. ECOSCAN accepts only bounded, typed, project/source-authorized inventory records through its own validation boundary.

The ECOSCAN OBIS adapter now exists and is covered by synthetic peer tests. It accepts an injected OBIS client, calls the versioned read-only capability `ecoscan.inventory.read`, and checks peer identity, recipient identity, project/source binding, measurement kinds, and local page/item budgets. The source project owns the Bridge and its provider credentials; ECOSCAN receives only authenticated, scoped inventory results and peer identity. No provider credential or credential reference is required inside ECOSCAN. The CLI intentionally does not register this adapter, and no remote peer or endpoint is configured. The current BRIDEX OBIS reference client/server is loopback-only and development-only, not production-ready. BRIDEX reference peers may provide optional development fixtures for the `ecoscan.inventory.read@1.0` capability and project/source grant checks; they are not the deployed Bridge and do not create a PR #66 or BRIDEX dependency. Any actual Bridge must be owned and operated by the relevant source project. Connection stages are optional: local acceptance first, generic OBIS conformance when needed, production transport/security review, then an explicitly approved read-only source pilot.

See [ECOSCAN Bridge Integration Plan](docs/ECOSCAN_BRIDGE_INTEGRATION_PLAN.md) for the topology, implemented adapter contract, capability payload, trust boundaries, staged gates, and independence tests.
