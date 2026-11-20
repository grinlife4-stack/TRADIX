# BRIDEX Engine 0.1 — Independent Engineering Plane

BRIDEX Engine creates, validates, packages, and verifies independent Bridge source projects. It is an offline engineering tool, not a Bridge runtime.

## Install

Requires Python 3.11 or newer.

~~~bash
python -m pip install -e ".[dev]"
~~~

## Create a new Bridge project

~~~bash
bridex init \
  --path ./my-bridge \
  --name "My Independent Bridge" \
  --owner-id "project:owner" \
  --owner-assignment-ref "approval:owner-001" \
  --operator-id "operator:primary" \
  --operator-assignment-ref "approval:operator-001"
~~~

The generator creates a unique `urn:uuid` Bridge ID unless one is explicitly supplied. Owner and operator are separate and both require assignment evidence.

Every generated project starts with:

- `lifecycle: draft`
- no trusted peers
- no declared or enabled capabilities
- OBIS transport and security profile marked `unconfigured`
- no credentials, secrets, network listeners, or outbound network client
- an explicit package file allowlist

BRIDEX does not infer ownership and does not activate a peer or capability.

## Validate, package, and verify

~~~bash
bridex validate --root ./my-bridge
bridex package --root ./my-bridge --output ./release/my-bridge-0.1.0.zip
bridex verify ./release/my-bridge-0.1.0.zip
~~~

Equivalent module invocation is available with `python -m bridex_engine`.

## Manifest and package rules

- Canonical manifest: `standards/bridex/0.1/bridge-manifest.schema.json`.
- The engine's packaged schema is checked byte-for-byte against the canonical schema in CI.
- Owner/operator assignment references, stable identity, independent runtime, OBIS profile declaration, capability scopes and limits, peer records, lifecycle, and package allowlist are explicit.
- Draft manifests cannot enable peers or capabilities.
- Only explicitly listed regular files are packaged. Symlinks, path traversal, secret/private-key paths, environment files, VCS/cache/dependency directories, and unlisted files are rejected.
- File and package sizes and archive entry counts are bounded.
- ZIP entries use stable ordering and timestamps. A package manifest records each included file's size and SHA-256.
- Verification checks the embedded Bridge manifest, exact file set, path safety, archive bounds, and every file hash. It never extracts or executes package content.

## Independence and limits

The engine has no TRADIX/BRIDEX runtime import, network access, listener, registry, relay, broker, credential store, or deployment function. A generated Bridge package does not need BRIDEX or TRADIX installed to run.

This is an engineering-plane generator and package verifier. It does not implement OBIS transport, authenticate peers, provision credentials, enable capabilities, or claim production conformance. Those are separate later stages.
