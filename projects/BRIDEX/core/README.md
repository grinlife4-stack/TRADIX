# BRIDEX Core — Package Foundation

**Package:** `bridex-core`  
**Version:** 0.1.0  
**Status:** Initial generic foundation; not a complete Bridge runtime or generator  
**Runtime dependency:** JSON Schema validator only  
**TRADIX/BRIDEX service dependency:** None

## Purpose

This package establishes a reusable, owner-portable package boundary for generated Bridge instances. It validates the machine-readable package manifest required to identify the Bridge, record its independently assigned owner/operator, describe supported contracts and approved peer scopes, inventory dependencies/licenses, and locate lifecycle/export instructions.

The manifest is metadata, not authority. Its contents do not authenticate a peer, grant permission, prove ownership by themselves, or authorize deployment. Ownership assignment evidence must be verified by the relevant parties. Peer scopes in the manifest are declarations of approved configuration, not runtime authorization enforcement.

## Included in 0.1

- Draft JSON Schema 2020-12 for a Bridge package manifest.
- Strict UTF-8 JSON loading with duplicate-key rejection.
- Schema validation with deterministic error ordering.
- Packaged schema accessible from an installed wheel.
- Portable package-directory verification.
- SHA-256 verification of the Bridge artifact.
- Validation of configuration and lifecycle file references.
- Rejection of path traversal and symlink escapes outside the package root.
- Deterministic ZIP export with normalized timestamps and file ordering.
- Safe restore with ZIP-slip, symlink/special-file, duplicate-path, entry-count, and uncompressed-size checks.
- Post-restore manifest and artifact verification.
- Positive and negative tests for ownership, unknown fields, duplicate keys, tampering, path traversal, and package verification.

## Manifest boundary

The manifest captures:
- Bridge identity and implementation version.
- Explicit owner and operator, with optional maintainer and ownership-record reference.
- Relative package artifact path and SHA-256 integrity value.
- Supported OBIS versions and replaceable adapter identifiers/versions.
- Configured peer identifiers and approved scope declarations.
- Provided/consumed capability declarations and scopes.
- Configuration-schema reference.
- Dependency version/license inventory.
- Build, deploy, backup, restore, upgrade, rollback, revocation, export, and decommissioning procedure references.

Secret values, credentials, tokens, private keys, customer payloads, and runtime state MUST NOT be embedded in this manifest.

## Portable package layout 0.1

An exported package has this minimum structure:

```text
bridge-package/
├── bridge-manifest.json
├── records/
│   └── ownership.json
├── artifact/
│   └── <bridge-artifact>
├── schemas/
│   └── config.schema.json
└── docs/
    └── lifecycle/
        ├── build.md
        ├── deploy.md
        ├── backup.md
        ├── restore.md
        ├── upgrade.md
        ├── rollback.md
        ├── revocation.md
        ├── export.md
        └── decommission.md
```

The ownership assignment record, artifact, configuration schema, and lifecycle documents are required files. All manifest file references are POSIX relative paths rooted inside the exported package. Absolute paths, parent traversal, and symlink escapes are rejected. The artifact's SHA-256 must match the manifest. The verifier does not extract or execute the artifact.

## Run independently

```bash
cd projects/BRIDEX/core
python -m pip install -e ".[dev]"
python -m pytest -q
```

The schema is packaged at `bridex_core/schemas/bridge-package-manifest.schema.json`. The installed `bridex-manifest` command exposes validation without requiring consumers to import package internals.

Validate a manifest:

```bash
bridex-manifest validate ./bridge-manifest.json
```

Verify an exported package:

```bash
bridex-manifest verify-package ./bridge-package

# Create a deterministic, owner-portable ZIP export
bridex-manifest export ./bridge-package ./bridge-package.zip

# Restore into a new directory and verify it before publishing
bridex-manifest restore ./bridge-package.zip ./restored-bridge
```

All commands exit with `0` on success and `2` for invalid input. Restore refuses to overwrite an existing destination.

## Deliberate limits

This package is not a Bridge runtime, code generator, transport adapter, OBIS implementation, trust store, credential manager, scheduler, retry engine, audit ledger, or production security profile. Package verification proves only the integrity and presence of the declared local package files. Export produces a deterministic ZIP of those files; restore validates archive paths and file types, restores into a new directory, and re-verifies the package. Neither operation proves that the artifact is safe, executable, interoperable, authorized, or production-ready.

Next generic foundation gates:
1. Add deterministic build/reproducibility metadata and export/restore tests.
2. Add an isolated conformance harness that consumes versioned OBIS test vectors without depending on Python peer internals.
3. Add lifecycle/health primitives only after their state transitions and failure semantics are specified.
4. Demonstrate a clean-environment install and execution with TRADIX and BRIDEX unavailable.

A valid package does not by itself satisfy OBIS conformance or production deployment acceptance.
