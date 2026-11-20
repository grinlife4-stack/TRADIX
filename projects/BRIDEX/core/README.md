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
- Positive and negative tests for required ownership, unknown fields, duplicate keys, and installed-package loading.

## Manifest boundary

The manifest captures:
- Bridge identity and implementation version.
- Explicit owner and operator, with optional maintainer and ownership-record reference.
- Package location and SHA-256 integrity value.
- Supported OBIS versions and replaceable adapter identifiers/versions.
- Configured peer identifiers and approved scope declarations.
- Provided/consumed capability declarations and scopes.
- Configuration-schema reference.
- Dependency version/license inventory.
- Build, deploy, backup, restore, upgrade, rollback, revocation, export, and decommissioning procedure references.

Secret values, credentials, tokens, private keys, customer payloads, and runtime state MUST NOT be embedded in this manifest.

## Run independently

```bash
cd projects/BRIDEX/core
python -m pip install -e ".[dev]"
python -m pytest -q
```

The schema is packaged at `bridex_core/schemas/bridge-package-manifest.schema.json`. The installed `bridex-manifest` command exposes the same validator without requiring consumers to import package internals.\n\nValidate a manifest with:\n\n```bash\nbridex-manifest validate ./bridge-manifest.json\n```\n\nThe command exits with `0` for a valid manifest and `2` for invalid or unreadable input.

## Deliberate limits / next generic-core work

This first slice is not a Bridge runtime, code generator, transport adapter, OBIS implementation, trust store, credential manager, scheduler, retry engine, audit ledger, or production security profile. Those concerns remain separate and must be implemented against approved contracts rather than guessed.

Next generic foundation gates:
1. Define and test a portable Bridge project/package layout and deterministic build metadata.
2. Add an isolated conformance harness that consumes versioned OBIS test vectors without depending on the Python peer internals.
3. Add lifecycle/health primitives only after their state transitions and failure semantics are specified.
4. Add export/restore and clean-environment tests proving no BRIDEX/TRADIX runtime dependency.

A valid manifest alone does not satisfy Bridge portability acceptance or OBIS conformance.
