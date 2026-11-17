# Product Portability Gate v1

## Purpose

Every product must describe how its source, runtime, dependencies, data, artifacts, configuration, and identity can move to another provider or a self-hosted environment. A product is not portable merely because its repository can be cloned.

The machine-readable contract is `schemas/product-portability-v1.schema.json`. A product dossier may reference its manifest through the optional `portability` field. The Hello World example uses `examples/hello-world/portability.json`.

## Commands

From the repository root:

```sh
python scripts/check_product_portability.py examples/hello-world/portability.json --mode design
python scripts/check_product_portability.py examples/hello-world/portability.json --mode release
```

- `design` validates that export/import procedures, dependency adapters and replacement plans, secret separation, backup/restore procedures, and exit-cost fields are documented.
- `release` additionally requires every portability component to be marked verified, evidence files with matching SHA-256 hashes, a successful restore test on a second isolated target, and an evidenced exit-cost/effort estimate.

The example is intentionally design-ready but not release-ready. CI asserts that design validation passes and release validation remains blocked.

## Evidence rules

Verified sections must include:
- `evidence_path`: a relative path contained beneath the manifest directory;
- `evidence_sha256`: the SHA-256 digest of that exact evidence file.

A passed restore test must additionally identify the isolated target and a timezone-aware test timestamp. Secret values must never be included in source control or portability exports; target credentials are re-enrolled through a secret-management process.

## Important limitation

The release checker validates the structure and integrity of supplied evidence. It does **not** execute exports, create backups, restore databases, copy object storage, or prove that a provider replacement works. Those actions must be performed in an isolated second environment and their actual output recorded as evidence before the release gate can pass.

Until that real restore rehearsal succeeds, portability remains a documented design and a blocked release criterion, not an achieved capability. No production migration, provider move, secret change, or paid-resource commitment is authorized by this gate.
