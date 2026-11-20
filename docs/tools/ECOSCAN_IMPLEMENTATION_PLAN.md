# ECOSCAN — Implementation Plan and MVP Boundary

**Document ID:** ECOSCAN-PLAN-001  
**Status:** Proposed engineering plan; no implementation or runtime authorization implied  
**Date:** 2026-11-20  
**Governing specification:** [ECOSCAN Specification](ECOSCAN_SPEC.md)  
**Reuse decision:** [Ready-Made Capability Audit](ECOSCAN_READY_MADE_CAPABILITY_AUDIT.md)

## 1. Objective

Build only the missing ECOSCAN orchestration and evidence layer. Reuse provider APIs, native filesystem metadata, and existing monitoring installations where appropriate. Do not build a new general-purpose monitoring platform.

ECOSCAN is a separately packageable and operable tool. TRADIX is its factory/toolbox, not its runtime requirement. A completed ECOSCAN installation must remain operable when TRADIX is unavailable.

## 2. MVP: narrow and verifiable

The first release is a **manual, read-only inventory engine** with explicit source selection and exportable evidence.

### Included in MVP

1. A versioned, declarative source registry with explicit project/source IDs, owner/operator, source type, non-secret locator, adapter ID, credential reference, and enabled state.
2. Manual scan command for exactly one selected source or an explicitly supplied set of sources.
3. Global, project, subsystem, and source enable/disable controls. The global disabled state blocks all scan execution and report publication.
4. A typed adapter interface with capability declarations and read-only enforcement.
5. A normalized measurement envelope with source timestamp, observation time, unit, measurement kind, method, adapter version, evidence, confidence, and coverage state.
6. Per-source budgets, bounded pagination, timeout, rate-limit handling, and resumable checkpoints.
7. Durable local state using Python standard-library SQLite, with schema versioning and explicit transactions.
8. Portable JSON and JSONL exports; CSV only for flat measurement tables. Import must validate schema and preserve original provenance.
9. Tests proving scope does not expand, disabled sources do not run, missing sources are not zero, and adapters cannot invoke write/delete operations through the ECOSCAN interface.

### Not in MVP

- Always-on polling, scheduler, background daemon, or hosted SaaS.
- Dashboard, alert delivery, or notification integrations.
- Automatic project discovery or broad account enumeration.
- Upload, delete, modify, lifecycle, resize, deployment, or billing operations.
- Downloading or hashing file contents.
- Cross-project credential sharing or a mandatory central database.
- Claims of exact physical/billed storage from logical object listings.
- Beszel, Prometheus, Zabbix, Grafana, or OpenTelemetry deployment unless an existing project already operates one and explicitly authorizes read-only integration.

## 3. Package and independence layout

Proposed location:

```text
projects/ECOSCAN/
  README.md
  pyproject.toml
  config/
    registry.schema.json
  src/ecoscan/
    __init__.py
    cli.py
    registry.py
    controls.py
    contracts.py
    planner.py
    runner.py
    measurements.py
    coverage.py
    store.py
    export.py
    adapters/
      filesystem.py
      github_metadata.py
      backblaze_b2.py
  tests/
    unit/
    contract/
    integration/
  docs/
    SECURITY.md
    DATA_MODEL.md
    OPERATIONS.md
```

This is a proposed package layout, not a statement that these files already exist.

The core should initially depend only on the Python standard library. Provider SDKs belong in optional extras, installed only for the selected adapter. The Backblaze adapter may reuse TRADIX's existing configuration/client implementation during development, but the released ECOSCAN package must own or vendor a properly licensed, independently maintained adapter implementation. It must not import `tradix.*` at runtime.

A generated package lock/export should record exact dependency versions and licenses. The source package and all required schemas/tests must be exportable without TRADIX runtime services.

## 4. Project data isolation

Default storage layout is project-separated:

```text
ECOSCAN_DATA_ROOT/
  projects/
    <project_id>/
      registry.json
      state.sqlite3
      exports/
      evidence/
  system/
    global-controls.json
```

- Each project has its own registry, history database, export directory, and owner-controlled retention policy.
- The system-level control file contains only the global enable/disable state and minimal orchestration metadata. It must not become a shared project data ledger.
- Cross-project reports are derived outputs. They do not merge source credentials, project databases, or ownership.
- A project can export its complete registry, history, evidence references, and schema version, then continue without ECOSCAN.
- If a project leaves the portfolio, its data remains independently usable. ECOSCAN removal does not delete it.
- Credentials remain in the source owner's secret manager or environment. The registry stores an opaque credential reference only.

## 5. Core contracts

### 5.1 Project registry and source descriptor

Each project's `registry.json` is one versioned project envelope:

- Registry fields: `schema_version`, `project_id`, and `sources[]`.
- Each source descriptor requires `source_id`, `owner_id`, `operator_id`, `subsystem_id`, `source_type`, `locator`, `adapter_id`, `adapter_version`, `credential_ref`, `enabled`, `budget`, `expected_measurements`, `retention_policy`, `created_at`, and `updated_at`.
- Optional source metadata includes `scope_tags`.
- `credential_ref` is nullable for local metadata; otherwise it is an opaque owner-controlled reference, never a secret value.
- Source IDs must be unique within the project registry. The JSON Schema validates each descriptor's shape; registry loading must enforce uniqueness and reject descriptors whose owner/operator/subsystem are not authorized for the project.

An empty `sources[]` is valid and means no sources are configured. No source is discovered or enabled implicitly. No secret values, private file contents, access tokens, or unrestricted discovery settings may be stored here.

### 5.2 Adapter interface

Each adapter exposes:

- `capabilities()`: supported measurement kinds, pagination/checkpoint support, and required read-only permissions.
- `validate_config(source)`: local validation without network access.
- `estimate_cost(source, budget)`: best-effort API/time estimate; unknown cost must remain UNKNOWN, not zero.
- `scan(source, checkpoint, budget)`: yields typed measurements and a resumable checkpoint.
- `health_check(source)`: optional, explicitly requested, bounded, and read-only.

No generic `execute`, `write`, `delete`, `upload`, or arbitrary command method is allowed in the adapter contract.

### 5.3 Measurement envelope

Every measurement includes:

- `measurement_id`, `project_id`, `source_id`
- `kind`: logical_bytes, allocated_bytes, physical_bytes, capacity_bytes, object_count, file_count, or provider_reported_usage
- `value`, `unit`, `measured_at`, `source_timestamp` (nullable)
- `method`, `adapter_id`, `adapter_version`
- `coverage_state`, `confidence`, `limitations`
- `evidence_ref` and `checkpoint_ref` (where applicable)

Measurements of unlike kinds or scopes must never be silently summed. A portfolio total is allowed only when measurement kind, unit, source semantics, and time window are comparable.

### 5.4 Coverage states

Use the specification's states: COMPLETE, PARTIAL, FAILED, NOT_CONFIGURED, NOT_AUTHORIZED, DISABLED. A source with no valid measurement is never represented as zero.

## 6. Initial adapters and selection order

### Adapter 1 — Local filesystem metadata

Purpose: prove the registry, controls, planner, runner, coverage, storage, and export behavior without any external account or secret.

- Operate only on explicit allowlisted paths.
- Do not follow symlinks outside the allowlist.
- Do not cross mount boundaries unless explicitly configured.
- Report logical bytes and file count separately; report allocated bytes only where the platform exposes reliable semantics.
- Never read file contents or compute hashes.
- Apply bounded traversal, cancellation, timeout, and resumable checkpoints.
- Tests use temporary directories and synthetic files only.

### Adapter 2 — GitHub repository metadata

Purpose: collect repository-level metadata through an explicitly authorized read-only token or public metadata where appropriate.

- No token is embedded in config or logs.
- Do not infer total storage from repository-size metadata.
- Git LFS, Actions artifacts, Packages, Releases, and external backups are distinct sources and require separate adapter capabilities.
- Pagination, rate limits, and token scopes are explicit.
- No repository content download, mutation, or secret enumeration.

### Adapter 3 — Backblaze B2 S3-compatible listing

Purpose: optional, owner-authorized, bucket-scoped current-object inventory.

- Reuse the existing `BackblazeConfig` and boto3 configuration behavior as a design reference; the independent ECOSCAN package must not depend on `tradix.*`.
- Use a non-master application key restricted to the named bucket and read/list permissions only. Do not use the existing write/read-back verification mode.
- Use paginated `ListObjectsV2` with bounded page count and checkpointing. Do not download object bodies.
- Report the sum of current visible object sizes as **current logical object bytes**, with object count and observation time.
- Do not call that value physical usage, billed storage, all-version storage, or exact account usage.
- S3 `ListObjectsV2` does not enumerate noncurrent object versions. Versioned storage and multipart/incomplete uploads need separate provider-specific inventory and permission review; if not measured, state the omission.
- Do not enable the adapter until the bucket owner authorizes it and current provider pricing, API request cost, retention/version behavior, and key scope are reviewed.
- A bucket per project/source is preferred where independent ownership and billing require it. Never place unrelated projects into a shared bucket merely for convenience.

### Adapter priority

Implement and prove the core with local filesystem fixtures first. Then add GitHub metadata only if a concrete registered source is approved. Add B2 last, after the read-only key and account eligibility are verified. No secrets are requested or provisioned by this plan.

## 7. Controls and execution state machine

The runner must fail closed and evaluate controls immediately before every page/request:

1. Global state must be ENABLED.
2. Project must be registered and ENABLED.
3. Subsystem must be ENABLED.
4. Source must be registered and ENABLED.
5. Requested scope must explicitly include the source.
6. Owner/operator authorization and credential reference must validate.
7. Budget and deadline must permit the next bounded operation.

If any gate fails, no adapter call is made and coverage is recorded as DISABLED, NOT_AUTHORIZED, or FAILED as appropriate. Disabling global execution must cancel active work at the next safe checkpoint and block report/alert publication. Manual scans never enable schedules.

## 8. Persistence and export rules

SQLite is a local implementation choice, not the data ownership boundary. Use one database per project by default. Schema migrations must be versioned, transactional, and tested against backups.

Export package:
- `manifest.json`: schema versions, project/source identifiers, export time, included ranges, and content hashes.
- `registry.json`: no secret values; credential references are redacted or mapped to owner-defined placeholders.
- `measurements.jsonl`: append-only measurement records with provenance.
- `coverage.jsonl`: scan attempts, failures, omissions, and control state.
- `evidence/`: only non-secret evidence explicitly allowed by the source owner.
- `README.txt`: import instructions and known limitations.

Import must reject unknown schema versions by default, preserve IDs and timestamps, and never reactivate disabled sources or schedules automatically.

## 9. Security model

- Default deny and explicit registration.
- Read-only adapter permissions; no write methods in the adapter contract.
- Secret values never enter registry, SQLite measurement rows, reports, exports, exceptions, or logs.
- Opaque credential references are resolved only by an owner-controlled provider.
- No arbitrary shell, command, filesystem path, or URL execution.
- URL and path validation must prevent SSRF, traversal, symlink escape, and accidental access to metadata endpoints or unrelated mounts.
- Rate limits, timeouts, bounded pagination, and concurrency caps are mandatory.
- Audit every scan start/stop, actor, scope, adapter version, result, and coverage gap.
- No cross-project credential reuse.
- No network source is contacted during registry validation or dry-run planning.

## 10. Implementation phases and exit criteria

### Phase 0 — Contract and threat review
- Approve this plan and resolve data retention, owner/operator identifiers, and local path policy.
- Define JSON Schema for registry, measurement, coverage, and export manifest.
- Threat-model local path traversal, SSRF, credential exposure, cross-project access, and resource exhaustion.
- Exit: schemas reviewed; negative tests specified; no runtime dependencies selected without evidence.

### Phase 1 — Core with synthetic/local fixtures
- Implement package skeleton, CLI, registry, controls, planner, typed adapter contract, local filesystem adapter, SQLite store, and JSON/JSONL export.
- Tests: exact scope, global switch, all lower-level switches, fail-closed permissions, no zero substitution, budget stop/resume, path traversal/symlink/mount boundary, export/import round trip.
- Exit: all tests pass; no network access or credentials required.

### Phase 2 — GitHub metadata adapter
- Implement only repository metadata fields that are available from documented read-only API endpoints.
- Add pagination, rate-limit handling, timestamp provenance, and explicit omissions for LFS/artifacts/packages.
- Exit: mocked contract tests plus one owner-authorized read-only integration test; no content download or write operation.

### Phase 3 — Backblaze B2 read-only adapter
- Implement paginated current-object listing with strict page/object/time budgets.
- Validate bucket-scoped read/list credentials and endpoint/region consistency.
- Report current logical bytes only; version and multipart omissions explicit.
- Exit: mocked pagination/continuation tests and a separately approved live read-only test. Do not run write-test.

### Phase 4 — Optional existing monitoring integrations
- Add Beszel, Prometheus, or Zabbix read-only adapters only if an existing project uses them and a real requirement exists.
- No new service deployment solely to satisfy ECOSCAN.
- Exit: adapter contract and owner-approved data boundary tests.

### Phase 5 — Portability and operational acceptance
- Export/import complete project data to a clean environment with no TRADIX imports.
- Disable/remove ECOSCAN and prove monitored projects and source resources remain unchanged.
- Test backup/restore, migration, and package installation without network services.
- Exit: independence acceptance suite passes; user approves any operational deployment separately.

## 11. Phase 0 evidence and remaining decisions

Phase 0 artifacts now exist:
- Four versioned JSON Schemas for source registry, measurement, coverage, and export manifest under `standards/ecoscan/0.1/`.
- A threat model and 20-row acceptance-test matrix.
- Automated Draft 2020-12 schema validation tests in `tests/test_ecoscan_schemas.py`.
- Explicit schema constraints for measurement kind/unit/value consistency, completed coverage timestamps, non-empty credential references, and safe relative export-path forms.
- Runtime obligations documented for credential-reference resolution, duplicate export paths, timestamp ordering, project/source ownership, and filesystem containment.

The latest completed CI on this branch passed **50 tests**, including the ECOSCAN schema tests, and built the TRADIX and OBIS reference wheels. This validates the current contract fixtures and repository test suite; it does not prove every cross-field/runtime invariant or authorize deployment.

Before moving from the foundation to a concrete scanner, review owner/operator identity evidence, data retention, local allowed-root/mount policy, checkpoint integrity, and export/import semantics. Continue using synthetic fixtures only. Do not begin network adapters or provision credentials before the relevant source owner explicitly authorizes them.


## 12. Phase 1 foundation — implemented

The independent package foundation now exists under `projects/ECOSCAN/`:

- Standalone Python package `ecoscan==0.1.0`, with no runtime third-party dependencies and no `tradix.*` imports.
- Strict project-registry parser for one project envelope containing multiple source descriptors; rejects duplicate source IDs, unknown fields, invalid identifiers, malformed budgets, and naive/inverted timestamps.
- Typed adapter protocol, per-scan budget guard, and single-source fail-closed runner with fake-adapter tests.
- Default-deny global, project, subsystem, and source controls.
- Explicit owner/operator authorization callback; absent authorization denies.
- Separate SQLite database per project, append-only measurement/coverage APIs, and separately replaceable scan checkpoints.
- Minimal offline CLI for registry validation and project-store initialization. It does not scan paths.
- Vendored schemas byte-compared with canonical files.
- CI installs and tests the package, builds a standalone wheel, installs it into an isolated target, and verifies packaged schema presence.

**Latest completed CI:** 64 tests passed. Both the OBIS and ECOSCAN wheels built; ECOSCAN installed in isolation and its schema resource was present.

Not implemented yet: concrete local filesystem adapter, safe traversal, resumable scanning, export/import, and provider integrations. The current package must not be described as a working scanner.

### Next engineering sequence

1. Implement a local filesystem adapter with explicit allowed roots, no-follow symlink handling, mount-boundary checks, bounded traversal, and resumable checkpoints.
2. Add end-to-end tests using synthetic temporary directories only.
3. Add export/manifest generation and a round-trip test before any provider adapter.
4. Only then consider separately authorized GitHub and Backblaze B2 adapters.


## 13. Explicit non-claims

This plan does not establish that:
- any B2 credentials are configured or working;
- any GitHub, B2, or host inventory has been scanned;
- exact physical or billed storage is measurable through current adapters;
- ECOSCAN is implemented, deployed, or operational;
- a monitoring service or cloud resource has been created.

Only completed tests and owner-authorized integration evidence may support those claims.
