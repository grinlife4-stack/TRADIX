# ECOSCAN Bridge Integration Plan

**Document ID:** ECOSCAN-BRIDGE-PLAN-001  
**Status:** Planned integration boundary; no live Bridge connection authorized  
**Applies to:** ECOSCAN Phase 1 and its future external-source integration  
**Protocol:** OBIS for independent external peer communication

## 1. Decision

ECOSCAN remains an independent, local-first inventory system. Its core registry, execution gate, bounded runner, per-project SQLite stores, and export/import pipeline must remain usable with no Bridge, TRADIX, BRIDEX, network, or cloud service available.

External provider connectivity is a separate integration layer. It must be implemented as an independently owned and deployable ECOSCAN Bridge instance, not as provider-specific network clients embedded in the ECOSCAN core.

The Bridge is a replaceable peer adapter. It is not a mandatory hub, relay, broker, registry, identity provider, or runtime dependency.

## 2. Intended topology

```text
External provider / system
        |
        | provider-specific API and least-privilege credentials
        v
Independent ECOSCAN Bridge
  - explicit owner and operator
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
- Owns its local registry, project/source identities, controls, scan history, measurement validation, and project-isolated storage.
- Decides which project/source may accept a measurement.
- Rejects unknown peers, unregistered source IDs, cross-project records, unsupported schemas, stale/expired messages, and unauthorized capabilities.
- Does not treat a successful OBIS handshake as authorization to write measurements.
- Remains fully usable in local-only mode when the Bridge is absent or disabled.

### ECOSCAN Bridge instance
- Has a separately assigned owner, operator, maintainer, identity, version, source/package, configuration, credentials, logs, and lifecycle.
- Holds only the provider credentials required for its explicitly assigned source and uses read-only scopes.
- Exposes narrow, typed inventory capabilities; it must not expose arbitrary shell, filesystem, database, or network-proxy operations.
- Performs provider-specific pagination, rate-limit handling, timestamp normalization, and bounded collection.
- Can be disabled, replaced, exported, moved, or operated without BRIDEX or TRADIX.

### BRIDEX and TRADIX
- BRIDEX may generate, package, and test the Bridge; it does not own it by default and is not required at runtime.
- TRADIX may catalogue build provenance and documentation. It must not become a runtime intermediary.
- Artifact Gateway and Tool Catalog may be optional package/evidence helpers only. Neither substitutes for OBIS authentication or authorization.

## 4. OBIS contract for the ECOSCAN integration

The Bridge integration must use OBIS as the independent peer-to-peer contract. It must explicitly declare:
- Bridge peer identity and ECOSCAN peer identity.
- Supported OBIS version and security profile.
- Narrow read-only capability identifiers and versions.
- Input/output schema references and versions.
- Project/source binding and permitted measurement kinds.
- Data classification, payload limits, request limits, TTL, timeout, and replay/idempotency behavior.
- Revocation behavior and audit/evidence references.

A proposed capability family is `ecoscan.inventory.read` for retrieving bounded provider inventory metadata and `ecoscan.measurement.submit` for submitting already-normalized measurement records. These names are proposals until the capability schemas and authorization rules are reviewed and versioned.

The receiving ECOSCAN peer must authorize every request independently. A Bridge may submit only for the project/source pair explicitly bound to its peer grant. It cannot choose or widen the project boundary from payload data alone.

## 5. Staged connection gates

1. **Local Phase 1 acceptance:** Complete and pass the local path-boundary, symlink, control-precedence, budget/timeout, corrupted-transfer, SQLite portability, and independence tests. No external connection is enabled.
2. **Bridge contract:** Version the ECOSCAN capability schemas, peer identity binding, project/source mapping, data classification, authorization, revocation, limits, and error behavior.
3. **Development conformance:** Use synthetic records and loopback-only peers. Prove valid/invalid peer, scope, replay, expiry, malformed payload, cross-project, timeout, and revocation behavior. This stage is not production approval.
4. **Production security profile:** Before any non-loopback connection, implement and independently review maintained TLS/mTLS or another approved authenticated transport, trust-anchor and certificate lifecycle, durable replay/idempotency, secret isolation, audit persistence, and operational revocation. The current BRIDEX OBIS reference prototype is loopback-only and its shared-secret HMAC profile is development-only.
5. **Provider pilot:** Only after explicit owner approval, select one synthetic or specifically authorized low-risk source, use read-only credentials held by the Bridge, and prove bounded operation and complete export/restore. No broad ecosystem scan.
6. **Expansion:** Add other providers only as separate Bridge-owned adapters after the previous source passes its own acceptance tests.

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
- No live connection or provider pilot is authorized by this plan.

## 8. Acceptance statement

The Bridge connection is a required future integration path, not a reason to weaken or bypass ECOSCAN's local independence. Phase 1 is accepted only on its own local evidence. The Bridge is accepted separately only after its OBIS security, authorization, portability, provider read-only, and failure-isolation gates pass.
