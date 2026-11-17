# TRADIX Project Capability Registry

**Status:** Prototype specification and implementation  
**Date:** 2026-11-17  
**Scope:** TRADIX control plane only

## Purpose

The Project Capability Registry records reusable capabilities created or adopted across the independent project portfolio. It provides a controlled path for a capability to move from a project-local proposal into the versioned TRADIX factory capability set.

The registry is not a package manager, code importer, deployment system, or automatic code promotion engine.

## Lifecycle

`project-local` → `proposed` → `accepted` → `deprecated`

A proposal may instead become `rejected`. Each capability version has an immutable descriptor. Status changes are appended as events; a new version is required for changed capability metadata or implementation.

## Required capability descriptor

- Stable capability identifier and semantic version.
- Originating project and accountable owner.
- Scope: `shared` or `product_specific`.
- Plain-language purpose and stable interface contract.
- Test reference and evidence reference.
- Changelog, compatibility statement, and deprecation policy.

The descriptor contains references and metadata only. It must not contain credentials, private keys, customer data, proprietary datasets, or executable payloads.

## Promotion gates

Promotion is explicit and fail-closed. All of the following must be true:

1. Security review passed.
2. License and provenance cleared.
3. Operational cost assessed.
4. Required tests passed.
5. Compatibility review passed.
6. Capability owner approved.
7. At least one concrete second-project use case or a documented factory-level need exists.
8. The proposal is marked `shared`, not `product_specific`.

The prototype records these decisions but does not independently verify the truth of evidence references. Reviewers remain accountable; future integrations must bind approvals to authenticated identities and verifiable evidence.

## Isolation rules

- Product-specific code and business logic remain in their product repository.
- Registry entries describe capabilities; they do not copy or execute product code.
- Products consume accepted capabilities only through explicit, versioned interfaces.
- Products pin versions and choose when to upgrade.
- A product must not require the TRADIX control plane at runtime merely to execute an already adopted capability.
- Failed or rejected experiments remain in the originating project.

## Prototype behavior

Implemented in `src/tradix/capabilities/registry.py` using Python standard-library SQLite:

- Persistent capability descriptors.
- Append-only status events.
- SQLite triggers preventing ordinary UPDATE/DELETE operations.
- Explicit proposal, promotion, rejection, deprecation, retrieval, and listing operations.
- Fail-closed promotion checks and semantic-version validation.

This is a local prototype, not a production security boundary. A database-file administrator can bypass SQLite triggers. The prototype has no identity provider, cryptographic reviewer signatures, external immutable anchor, distributed concurrency model, artifact/package publisher, or CI evidence verifier.

## Next acceptance gates

1. Run the complete project test suite on the exact PR head.
2. Review API and schema for compatibility and security.
3. Add authenticated reviewer identity and signed decision receipts before any real promotion authority is delegated.
4. Add externally anchored audit evidence before relying on the ledger for high-assurance governance.
5. Define capability package distribution and project-side pinning as a separate feature; do not bundle code execution into the registry.
