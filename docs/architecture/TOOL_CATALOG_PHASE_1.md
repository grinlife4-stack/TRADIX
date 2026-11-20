# TRADIX Tool Catalog — Phase 1

**Status:** Initial read-only metadata catalog prototype  
**Date:** 2026-11-17  
**Scope:** TRADIX factory control plane

## Purpose

The Tool Catalog records which external or local tools may be useful, what they declare they support, their license/platform constraints, and their review lifecycle.

It is separate from the Project Capability Registry:
- Tool Catalog: external/local tools and adapter candidates.
- Capability Registry: reusable TRADIX-owned capabilities proposed for controlled promotion.
- Neither registry executes code or stores credentials.

## Lifecycle

`discovered → evaluated → approved → connected`

Tools may be suspended from any non-retired state. Evaluated or approved tools may be retired. Suspended tools may be re-evaluated or approved again. Retired is terminal.

The prototype records metadata and append-only lifecycle events. Evaluation, approval, and connection transitions require evidence references. A connected state is only a recorded claim; a future adapter health-check service must verify it before it is trusted operationally.

## Descriptor

Each immutable tool-version descriptor records stable ID/version, category, upstream HTTPS source, license identifier, supported platforms, declared capabilities, execution modes, adapter contract version, free/open-source assertion, and notes.

The `free_open_source` field is a catalog assertion, not a legal conclusion. License and source evidence must be reviewed before approval. Hosted free tiers, quotas, paid services, and commercial terms must not be mislabeled as free/open-source software.

## Safety boundaries

- Metadata only: no installation, shell execution, network probing, credential storage, or deployment.
- No automatic trust based on popularity or vendor claims.
- Tool descriptors are immutable per version; corrections require a new version.
- Events are append-only under ordinary SQLite operations, but triggers are not tamper-proof against a database-file administrator.
- Evidence references are not automatically verified.
- The catalog does not establish that a tool is installed, reachable, healthy, or authorized.
- No automatic replacement is claimed; replacements must pass the same adapter contract and acceptance tests.

## Acceptance criteria

- Register and retrieve versioned metadata.
- Filter by lifecycle state and category.
- Persist across restarts.
- Reject malformed descriptors and duplicate versions.
- Enforce explicit lifecycle transitions and evidence references.
- Preserve lifecycle history.
- Block ordinary record/event mutation.
- Perform no arbitrary execution or external side effects.

## Initial candidates (not connected)

Flutter, Gradle, Android SDK, Xcode/macOS runners, Fastlane, GitHub Actions, Playwright, pytest, Docker/OCI tooling, OSV-Scanner, Trivy, Semgrep, and Ruff are candidates for evaluation only. Current versions, licenses, platform requirements, maintenance, quotas, and security posture must be checked against upstream evidence before approval.

## Next phase

Implement a read-only inventory/import path and adapter contract tests. Only then consider narrowly allowlisted execution adapters. General-purpose agents must not receive arbitrary shell access or signing/deployment secrets.
