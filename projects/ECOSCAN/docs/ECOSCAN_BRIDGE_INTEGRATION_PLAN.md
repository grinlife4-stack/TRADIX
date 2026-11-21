# ECOSCAN Bridge Integration Plan

**Document ID:** ECOSCAN-BRIDGE-PLAN-001  
**Status:** OBIS adapter implemented and synthetic-tested; live Bridge connection not enabled  
**Applies to:** ECOSCAN Phase 1 and its future external-source integration  
**Protocol:** OBIS for independent external peer communication

## 1. Decision

ECOSCAN remains an independent, local-first inventory system. Its core registry, execution gate, bounded runner, per-project SQLite stores, and export/import pipeline must remain usable with no Bridge, TRADIX, BRIDEX, network, or cloud service available.

External provider connectivity is a separate integration layer. It must be implemented as an independently deployable Bridge instance owned by the project that owns the external source/resource being inventoried, not by ECOSCAN by default and never by BRIDEX. Provider-specific network clients must not be embedded in the ECOSCAN core.

The Bridge is an optional, replaceable peer adapter for sources that require external access. It is not a mandatory component of ECOSCAN, hub, relay, broker, registry, identity provider, or runtime dependency.

### 1.1 Permanent engineering-capability integration

ECOSCAN also uses the ecosystem Bridge standard for its own engineering lifecycle. Through explicitly authorized OBIS peers, it may access relevant engineering tools and capabilities exposed by TRADIX and BRIDEX during initial construction, testing, maintenance, and later development. This is an ongoing capability path, not a one-time bootstrap connection.

This engineering path is distinct from the operational source Bridges described below:
- A Bridge exposing TRADIX capabilities is owned and controlled by TRADIX; a Bridge exposing BRIDEX capabilities is owned and controlled by BRIDEX. BRIDEX's role as Bridge engineer does not transfer ownership of a TRADIX Bridge or any other project's Bridge to BRIDEX.
- ECOSCAN receives only approved peer identity, non-secret connection metadata, and narrowly scoped capability grants. Credentials remain with the project that owns and operates the exposing Bridge.
- Engineering access is available when authorized and needed; it does not create a mandatory network session or make BRIDEX/TRADIX a runtime dependency of ECOSCAN's standalone inventory functions.
- These links are not the same Bridge instances or trust grants used to read operational resources from other projects.

The exact endpoints and capability grants are not configured or live. This plan does not authorize a production connection.

## 2. Intended topology

```text
External provider / system
        |
        | provider-specific API and least-privilege credentials
        v
Independent source-project-owned Bridge
  - owner: project that owns the exposed source/resource
  - separately appointed operator and maintainer
  - provider-specific adapter
  - credential isolation
  - bounded read-only inventory capabilities
  - independent audit and lifecycle
        |
        | OBIS peer-to-peer exchange
        v
ECOSCAN OBIS ingress adapter
        |
        | validated, bounded inventory records
        v
ECOSCAN adapter contract / runner
        |
        v
Project-isolated SQLite stores
        |
        +--> JSON / JSONL export and independent restore
```

ECOSCAN does not receive provider credentials. The Bridge must not receive permission to modify provider resources. The ECOSCAN side independently validates peer identity, capability, scope, payload schema, timestamps, expiry, and project/source attribution before accepting measurements.

## 3. Responsibility and trust boundaries

### ECOSCAN
- Owns its local registry, project/source identities, controls, scan history, measurement validation, receiving adapter, and project-isolated storage.
- Decides which project/source may accept a measurement.
- Rejects unknown peers, unregistered source IDs, cross-project records, unsupported schemas, stale/expired messages, and unauthorized capabilities.
- Does not treat a successful OBIS handshake as authorization to write measurements.
- Remains fully usable in local-only mode when the Bridge is absent or disabled.

### Source-project-owned Bridge instance
- Is owned by the project whose external source/resources it exposes to ECOSCAN; BRIDEX never owns it.
- Has a separately appointed operator and maintainer, its own identity, version, source/package, configuration, provider credentials, logs, and lifecycle.
- Holds only the provider credentials required for its explicitly assigned source and uses read-only scopes.
- Exposes narrow, typed inventory capabilities; it must not expose arbitrary shell, filesystem, database, or network-proxy operations.
- Performs provider-specific pagination, rate-limit handling, timestamp normalization, and bounded collection.
- Can be disabled, replaced, exported, moved, or operated without BRIDEX or TRADIX.

### BRIDEX and TRADIX
- BRIDEX may generate, package, test, and optionally maintain the Bridge under the source project's direction; it never owns or centrally operates the project Bridge and is not required at runtime.
- TRADIX may catalogue build provenance and documentation. It must not become a runtime intermediary.
- Artifact Gateway and Tool Catalog may be optional package/evidence helpers only. Neither substitutes for OBIS authentication or authorization.

## 4. OBIS contract for the ECOSCAN integration

When an optional Bridge integration is enabled, it must use OBIS as the independent peer-to-peer contract. It must explicitly declare:
- Bridge peer identity and ECOSCAN peer identity.
- Supported OBIS version and security profile.
- Narrow read-only capability identifiers and versions.
- Input/output schema references and versions.
- Project/source binding and permitted measurement kinds.
- Data classification, payload limits, request limits, TTL, timeout, and replay/idempotency behavior.
- Revocation behavior and audit/evidence references.

The optional inventory capability contract is `ecoscan.inventory.read@1.0`, requiring the read-only scope `ecoscan:inventory:read`. The ECOSCAN adapter is implemented in `src/ecoscan/obis_bridge.py`. It accepts an injected authenticated OBIS client and endpoint, verifies sender/recipient identity and project/source binding in the response, enforces local page/item budgets, and maps only the declared `logical_bytes` and `file_count` measurements. BRIDEX reference code contains a matching development helper, but it is only a test/reference implementation and does not own or constitute the source project's deployed Bridge. A separate `ecoscan.measurement.submit` capability is not part of this read-only integration.

The receiving ECOSCAN peer must authorize every request independently. A Bridge may expose inventory only for the project/source pair explicitly bound to its peer grant. It cannot choose or widen the project boundary from payload data alone.

## 5. Staged connection gates

1. **Local Phase 1 acceptance:** Complete and pass the local path-boundary, symlink, control-precedence, budget/timeout, corrupted-transfer, SQLite portability, and independence tests. No external connection is enabled.
2. **Bridge contract:** The initial `ecoscan.inventory.read@1.0` adapter contract and synthetic conformance tests now exist. The source-project-owned Bridge implementation must register that exact capability and independently bind its authenticated peer grant to the allowed project/source. Revocation, production transport, and durable replay handling remain additional requirements.
3. **Development conformance:** ECOSCAN CI synthetic tests cover successful adapter invocation, peer mismatch, and cross-project rejection. A generic OBIS peer fixture may be used to test the adapter contract and wire behavior. BRIDEX's reference Python/Go peers may be optional fixtures, but an ECOSCAN-to-BRIDEX-specific wire test is not a required acceptance gate and does not prove that a source project's own Bridge is deployed or authorized. The current synthetic tests do not prove a live project-owned Bridge integration or production readiness.
4. **Production security profile:** Before any non-loopback connection, implement and independently review maintained TLS/mTLS or another approved authenticated transport, trust-anchor and certificate lifecycle, durable replay/idempotency, secret isolation, audit persistence, and operational revocation. The current BRIDEX OBIS reference prototype is loopback-only and its shared-secret HMAC profile is development-only.
5. **Provider pilot:** Only after explicit owner approval, select one synthetic or specifically authorized low-risk source, use read-only credentials held by the Bridge, and prove bounded operation and complete export/restore. No broad ecosystem scan.
6. **Expansion:** Add other providers only through separately owned Bridge instances controlled by the relevant source projects, after each source passes its own acceptance tests.

## 6. Required failure and independence tests

- ECOSCAN local-only scans and exports still work with the Bridge process stopped.
- The Bridge cannot write, delete, deploy, resize, or change provider resources.
- An unknown or revoked Bridge peer is rejected.
- A valid peer with an unapproved capability or scope is rejected.
- A Bridge cannot submit measurements for another project or source.
- Invalid, oversized, expired, replayed, duplicated, or schema-invalid messages are rejected before storage.
- Bridge timeout, crash, or network loss creates a coverage gap, never a zero-usage measurement.
- Disabling the global/project/subsystem/source switch prevents Bridge-originated measurements from being committed.
- Stopping TRADIX, BRIDEX, Artifact Gateway, or Tool Catalog does not interrupt an already installed and authorized Bridge.
- Exported ECOSCAN records remain restorable without the Bridge or TRADIX.

## 7. Explicit non-goals and prohibitions

- No GitHub, Backblaze B2, S3/R2, Railway, or other provider client is added to the ECOSCAN core.
- No credentials, tokens, private endpoints, or real project paths are stored in source control.
- No automatic peer discovery or implicit trust.
- No production use of the current loopback-only OBIS prototype.
- No mandatory BRIDEX/TRADIX service, shared relay, central broker, or shared cross-project database.
- The adapter is not registered by the Phase 1 CLI and no live connection or provider pilot is authorized by this plan.

## 8. Acceptance statement

Bridge connectivity is an optional future capability, not a requirement for ECOSCAN completion or operation. Phase 1 is accepted on its own local evidence. Any source-project-owned Bridge is accepted separately only after its OBIS security, authorization, portability, provider read-only, ownership, and failure-isolation gates pass.


## 9. Implemented adapter contract and current connection status

The ECOSCAN package now contains `src/ecoscan/obis_bridge.py`. Its transport is dependency-injected: the caller supplies an OBIS client that is responsible for authenticating the peer, verifying response signatures, applying expiry/replay protection, and keeping credentials outside ECOSCAN. The adapter never imports a network client or reads a secret.

The adapter invokes `ecoscan.inventory.read@1.0` with `ecoscan:inventory:read`, passing only the registered project ID, source ID, and requested measurement kinds. It rejects mismatched sender/recipient identity, project/source mismatch, unexpected result fields, unsupported measurement kinds, invalid counters, and budget overflow. The local runner remains the final authority and commits no measurement if adapter validation fails.

Synthetic tests exercise the injected-client boundary. They do not yet constitute a live OBIS wire test. The CLI intentionally registers only the local filesystem adapter. The source project must configure and operate its own Bridge endpoint, peer identity, provider credentials, and secret injection. ECOSCAN must be configured only with the approved peer identity, source/project grant, and non-secret connection metadata; it must never receive the provider credential or its secret reference. The generic OBIS loopback reference implementation may be used as an optional development fixture, but its HTTP/HMAC profile must not be exposed beyond loopback or treated as production security. It is not a substitute for a Bridge owned and operated by the source project.


## 10. Bridge-side credential grant mapping

BRIDEX maintains optional reference implementations and conformance fixtures; these are not the deployed source-project Bridge. Each source-project Bridge credential must be provisioned by that project's owner with only the allowed `(project_id, source_id)` pairs for its peer relationship. The authenticated OBIS peer must reject an out-of-grant payload before calling the provider. The Bridge provider callback then performs only the approved metadata read and returns the typed result expected by ECOSCAN.

The two sides now share these exact values:
- Capability: `ecoscan.inventory.read`
- Version: `1.0`
- Scope: `ecoscan:inventory:read`
- Project/source payload keys: `project_id`, `source_id`
- Measurement kinds: `logical_bytes`, `file_count`

This establishes a development integration contract only. It does not claim that a source-project-owned Bridge, live endpoint, credentials, production transport, or end-to-end integration is configured or accepted.

## Absolute scan deadline enforcement

The local BudgetGuard establishes one monotonic deadline from the smaller of
timeout_seconds and max_duration_seconds. The OBIS adapter passes that absolute
deadline into the injected client's invoke contract and checks it again
immediately after the call returns. ScanRunner performs a final deadline check
before validating or committing any adapter result, including an empty result
with zero reported items.

The BRIDEX Python reference client enforces the deadline across the complete
loopback HTTP exchange, including slow-drip response bodies, and shuts down
the active socket when the deadline expires. A transport timeout that coincides
with the scan deadline is recorded as FAILED / budget_exhausted; a shorter
client-specific transport timeout remains a distinct adapter execution failure.
Failure coverage is committed with no measurements.

A timeout does not prove the remote provider did not execute. The peer may
have completed the operation before the response was cut off. ECOSCAN persists
a durable operation intent before dispatch. After restart, the runner can query
the authenticated OBIS 0.2 status endpoint and reconcile only a committed
terminal outcome; it never resubmits the operation. Unknown/not-found status
remains unresolved. Reconciliation evidence is appended to a separate SQLite
table and included in portable exports; the original INDETERMINATE coverage
record is never overwritten. This is owner-local recovery, not distributed
exactly-once execution or production audit certification. The current OBIS
reference remains loopback-only and development/conformance-only, not a
production transport.

