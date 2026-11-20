# ECOSCAN

**Status:** Phase 1 foundation in development. No network adapters, scheduled scans, credentials, or deployment are included.

ECOSCAN is an independently packageable, read-only resource inventory tool. It must remain operable without TRADIX. This package currently provides:

- Strict parsing of the project registry envelope and unique source IDs.
- Typed adapter contract, explicit budget guard, and single-source fail-closed scan runner.
- Default-deny global/project/subsystem/source controls.
- Explicit owner/operator authorization callback; absence of an authorizer denies execution.
- One SQLite database per project, with append-only measurement and coverage records.
- A separately replaceable checkpoint store.
- Vendored 0.1 contract schemas, byte-compared against the canonical repository schemas.

The concrete local filesystem adapter is not yet implemented and no production adapter is registered. The runner is exercised with fake adapters only. The current CLI only validates a registry or initializes a project-local database; it does not scan any path.

## Install

```bash
python -m pip install -e .
```

Development tests:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```

## CLI

```bash
ecoscan validate-registry path/to/registry.json
ecoscan init-store --data-root ./ecoscan-data --project-id project-a
```

The data root is caller-selected. Do not point it at production project data until the data-retention and access policy is approved.

## Independence and security boundary

- Runtime dependencies are Python standard library only.
- No `tradix.*` imports.
- No secrets are accepted in registry fields; `credential_ref` is an opaque reference only.
- No network calls, arbitrary command execution, file-content reads, or source discovery.
- All controls default to disabled and authorization defaults to deny.
- Each project's database is stored under its own project ID.
