# ECOSCAN Bridge Integration Plan

**Document ID:** ECOSCAN-BRIDGE-PLAN-001  
**Status:** OBIS adapter implemented and synthetic-tested; live Bridge connection not enabled  
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

The first capability is now fixed for this integration: `ecoscan.inventory.read` version `1.0`, requiring the read-only scope `ecoscan:inventory:read`. The ECOSCAN adapter is implemented in `src/ecoscan/obis_bridge.py`. It accepts an injected authenticated OBIS client and endpoint, verifies sender/recipient identity and the project/source binding in the response, enforces local page/item budgets, and maps only the declared `logical_bytes` and `file_count` measurements. The BRIDEX reference peer now has a matching server-side helper in PR #66, with per-credential `allowed_resources` pairs enforced before the provider callback. A separate `ecoscan.measurement.submit` capability is not part of this read-only integration.

The receiving ECOSCAN peer must authorize every request independently. A Bridge may submit only for the project/source pair explicitly bound to its peer grant. It cannot choose or widen the project boundary from payload data alone.

## 5. Staged connection gates

1. **Local Phase 1 acceptance:** Complete and pass the local path-boundary, symlink, control-precedence, budget/timeout, corrupted-transfer, SQLite portability, and independence tests. No external connection is enabled.
2. **Bridge contract:** The initial `ecoscan.inventory.read@1.0` adapter contract and synthetic conformance tests now exist. The Bridge implementation must register that exact capability and independently bind its authenticated peer grant to the allowed project/source. Revocation, production transport, and durable replay handling remain additional requirements.
3. **Development conformance:** ECOSCAN CI synthetic tests cover successful adapter invocation, peer mismatch, and cross-project rejection. BRIDEX PR #66 adds loopback HTTP tests for the matching server capability, including project/source grant rejection before provider execution. A combined ECOSCAN-adapter-to-BRIDEX-server wire test and fresh CI on PR #66's latest head are still pending. The current separate tests do not yet prove end-to-end interoperability and this stage is not production approval.
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
- The adapter is not registered by the Phase 1 CLI and no live connection or provider pilot is authorized by this plan.

## 8. Acceptance statement

The Bridge connection is a required future integration path, not a reason to weaken or bypass ECOSCAN's local independence. Phase 1 is accepted only on its own local evidence. The Bridge is accepted separately only after its OBIS security, authorization, portability, provider read-only, and failure-isolation gates pass.


## 9. Implemented adapter contract and current connection status

The ECOSCAN package now contains `src/ecoscan/obis_bridge.py`. Its transport is dependency-injected: the caller supplies an OBIS client that is responsible for authenticating the peer, verifying response signatures, applying expiry/replay protection, and keeping credentials outside ECOSCAN. The adapter never imports a network client or reads a secret.

The adapter invokes `ecoscan.inventory.read@1.0` with `ecoscan:inventory:read`, passing only the registered project ID, source ID, and requested measurement kinds. It rejects mismatched sender/recipient identity, project/source mismatch, unexpected result fields, unsupported measurement kinds, invalid counters, and budget overflow. The local runner remains the final authority and commits no measurement if adapter validation fails.

Synthetic tests exercise the injected-client boundary. They do not yet constitute a live OBIS wire test. The CLI intentionally registers only the local filesystem adapter. A real Bridge endpoint, peer IDs, credential reference, and runtime secret injection must be supplied by the owner after local Phase 1 acceptance. The BRIDEX loopback reference implementation may be used for the next development conformance step, but its HTTP/HMAC profile must not be exposed beyond loopback or treated as production security.


## 10. Bridge-side credential grant mapping

The matching BRIDEX reference implementation is being developed in [TRADIX PR #66](https://github.com/grinlife4-stack/TRADIX/pull/66). Each Bridge credential must be provisioned with only the allowed `(project_id, source_id)` pairs for its peer relationship. The server capability uses `resource_binding=True`, so the authenticated OBIS peer rejects an out-of-grant payload before calling the provider. The Bridge provider callback then performs only the approved metadata read and returns the typed result expected by ECOSCAN.

The two sides now share these exact values:
- Capability: `ecoscan.inventory.read`
- Version: `1.0`
- Scope: `ecoscan:inventory:read`
- Project/source payload keys: `project_id`, `source_id`
- Measurement kinds: `logical_bytes`, `file_count`

This establishes the integration contract and the two independent implementations. It does not claim that a live endpoint is configured or that the combined end-to-end test has passed.
