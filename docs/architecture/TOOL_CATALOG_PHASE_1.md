# TRADIX Tool Catalog — Phase 1

**Status:** Metadata-only catalog prototype  
**Scope:** TRADIX factory control plane

## Purpose

The Tool Catalog records external or local tool candidates and their declared versions, licenses, platforms, capabilities, execution modes, and review lifecycle. It is separate from the Project Capability Registry: one inventories tools; the other promotes reusable TRADIX-owned capabilities.

## Implemented behavior

- File-backed SQLite persistence.
- Immutable versioned descriptors and append-only lifecycle events under ordinary SQL operations.
- Lookup and filtering by lifecycle state or category.
- Explicit lifecycle transitions: discovered, evaluated, approved, connected, suspended, retired.
- Evidence references required for evaluation, approval, and connection transitions.
- Descriptor validation for version syntax, tool IDs, HTTPS source URLs, unique platform/capability lists, and bounded metadata.
- Transactional lifecycle updates with SQLite foreign keys, busy timeout, and FULL synchronous mode.

## Lifecycle meaning and limits

- discovered: metadata has been recorded only.
- evaluated: a review was recorded with an evidence reference.
- approved: an approval assertion is recorded with evidence. The catalog does not authenticate the actor or cryptographically verify the approval.
- connected: an operator recorded a connection/health-check evidence reference. This is not a live health check performed by this catalog.
- suspended: use is administratively blocked in the catalog.
- retired: terminal lifecycle state.

Evidence references are validated for basic URI shape, not fetched or verified. SQLite triggers prevent ordinary updates/deletes but are not tamper-proof against an administrator who can replace or edit the database file. This is not a signed audit ledger.

## Security boundaries

This catalog is metadata-only. It does not install packages, run shell commands, probe networks, store credentials, authenticate users, or deploy software. Registration is not approval, and a catalog status does not grant runtime execution permission.

Tool descriptors are immutable per version. Corrections require registering a new version. free_open_source is an assertion for review, not a legal determination. Hosted free tiers and quotas must not be mislabeled as open-source software.

## Tests

The repository CI runs catalog tests alongside the artifact intake/gateway suite. Passing tests establish tested local behavior only; they do not establish that listed tools are installed, reachable, licensed for a particular use, or safe to execute.

## Next phase

Add a read-only import/inventory path with source evidence, then define a versioned adapter contract and contract tests. Do not add arbitrary command execution or expose credentials to agents.
