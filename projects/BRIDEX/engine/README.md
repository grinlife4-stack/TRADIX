# BRIDEX Engine — Phase 1

This is the independent engineering-plane package for validating Bridge manifests and producing deterministic, integrity-verifiable source packages.

## Install

Requires Python 3.11 or newer.

```bash
python -m pip install -e ".[dev]"
```

## Commands

Run from a Bridge source directory containing an explicit `bridge.json` manifest:

```bash
bridex validate --root ./my-bridge
bridex package --root ./my-bridge --output ./release/my-bridge-0.1.0.zip
bridex verify ./release/my-bridge-0.1.0.zip
```

Equivalent module invocation is available with `python -m bridex_engine`.

## Manifest and package rules

- The canonical manifest contract is `standards/bridex/0.1/bridge-manifest.schema.json`.
- Each Bridge must declare its stable identity, version, owner, operator, OBIS version/profile identifiers, independent runtime declaration, capabilities, scopes, side-effect class, payload bounds, and explicit package file list.
- Owner and operator are separate fields; BRIDEX does not assign ownership.
- Only explicitly listed regular files are packaged. Symlinks, path traversal, credential/private-key paths, environment files, VCS/cache/dependency directories, and unlisted files are rejected.
- Package size and individual file sizes are bounded.
- ZIP entries use stable ordering and timestamps. A package manifest records each included file's size and SHA-256.
- Verification checks the embedded Bridge manifest, exact file set, path safety, archive bounds, and every file hash. Verification never extracts or executes package content.

## Boundaries

This is BRIDEX engineering-plane tooling. It is not a Bridge runtime, network service, OBIS transport, authentication provider, credential store, registry, relay, or broker. Generated Bridge packages do not need BRIDEX installed to run. The engine performs no network access and does not execute source code.

Phase 1 validates and packages an existing Bridge source tree; it does not yet scaffold project-specific source code or claim OBIS production conformance. Those are later gates.
