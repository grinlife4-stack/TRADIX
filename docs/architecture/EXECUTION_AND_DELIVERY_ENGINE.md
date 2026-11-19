# TRADIX Execution & Delivery Engine

**Status:** Architecture proposal; orchestration implementation remains pending.

The factory should orchestrate mature tools through versioned, vendor-neutral adapters rather than reimplementing compilers, test runners, signing systems, deployment clients, or monitoring products.

## Delivery chain

Request → Project specification → Plan → Tool selection → Execution → Verification → Artifact → Approval → Delivery → Monitoring

Every stage must emit structured evidence bound to a durable run record. A successful command is not proof of a successful delivery.

## Core subsystems

1. Tool Catalog: versioned metadata, license/source/platform declarations, lifecycle, and evidence references. The Phase 1 metadata-only implementation is separate from this document.
2. Adapter contract: health checks, capability discovery, bounded execution, cancellation, logs, artifact references, and normalized errors.
3. Orchestrator: dependency graph, runner selection, idempotency, bounded retries, timeouts, and durable state transitions.
4. Verification: bind source SHA, dependencies, toolchain, test results, artifact digest, and approval. Missing or stale evidence blocks delivery.
5. Artifact registry: metadata, hashes, provenance, retention, compatibility, promotion, and rollback references. Large binaries remain in object storage.
6. Delivery connectors: provider-specific publication APIs behind separate adapters. External publication, purchases, payments, DNS changes, and production deployment require explicit owner approval.

## Security and authority boundaries

- Planner, implementer, tester, reviewer, and release permissions must be separated.
- Untrusted project code never runs inside the control-plane process.
- Secrets are injected only into the trusted step that requires them and are redacted from logs.
- External side effects are disabled by default.
- All work is bound to pinned source commits.
- A missing or failed verifier blocks delivery.
- Human approval remains mandatory for production release and irreversible actions.

## Implementation phases

1. Inventory and metadata-only catalog.
2. Narrow allowlisted execution adapters using existing CI and local test commands.
3. Immutable run receipts and artifact provenance.
4. Android sample build and verification; iOS requires a macOS/Xcode runner.
5. Generalize only capabilities proven by a second independent project.

## Explicit non-claims

This document does not claim that any candidate tool is installed, connected, healthy, licensed for a particular project, or authorized for execution. No mobile application has been built, signed, submitted, or published by this proposal.
