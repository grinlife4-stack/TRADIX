# Standalone OBIS Python Reference Peer

This is a small, independently installable reference implementation for the OBIS 0.1 draft. It is intentionally located outside the TRADIX runtime package and has **no runtime dependency on TRADIX or BRIDEX**.

## What is executable
The canonical draft schema is published independently at [standards/obis/0.1/message.schema.json](../../../../standards/obis/0.1/message.schema.json). The Python package includes a byte-identical copy for offline installation; CI checks that they do not drift.


- Direct HTTP request/response between two separately instantiated peers.
- Version and message validation.
- Peer/principal binding to an explicitly configured credential.
- HMAC-SHA256 message and response integrity for the local conformance profile.
- Explicit capability registration and least-privilege scope checks.
- Optional credential-bound resource grants for capabilities that must be restricted to explicit project/source pairs.
- ECOSCAN read-only inventory capability registration with strict schema and measurement bounds.
- Loopback HTTP tests for a valid ECOSCAN inventory request and rejection of a project/source outside the credential grant before the provider handler runs.
- Expiry, maximum TTL, payload-size limits, and nonce replay rejection. The default guard is in-memory for development; an optional owner-local SQLite guard persists replay state across process restarts and fails closed on storage errors.
- Correlated and signed responses.
- Negative tests for spoofing, unknown credentials, excess scopes, replay, expiry, unsupported versions, unknown capabilities, and oversized payloads.

## Run locally

Requires Python 3.11 or newer. No runtime dependencies are required.

```bash
cd projects/BRIDEX/reference/obis-python
python -m pip install -e ".[dev]"
python -m pytest -q
```

## ECOSCAN inventory capability

The optional `register_ecoscan_inventory_capability` helper registers `ecoscan.inventory.read@1.0`. Each credential must carry an explicit `allowed_resources=frozenset({(project_id, source_id)})` grant. The OBIS peer checks this binding after authentication and scope authorization but before invoking the provider handler. The provider callback is responsible for metadata-only reads and must not modify the connected project.

## Minimal two-peer example

```python
from obis_bridge import Credential, OBISClient, OBISPeer, OBISServer

secret = b"replace-this-test-secret-with-at-least-32-bytes"
credential = Credential(
    key_id="peer-a-key",
    peer_id="peer:a",
    principal_ref="principal:a",
    secret=secret,
    allowed_scopes=frozenset({"catalog:read"}),
)

peer_b = OBISPeer("peer:b", [credential])
peer_b.register_capability(
    "catalog.lookup", "1.0", {"catalog:read"},
    lambda payload: {"found": payload["item_id"] == "demo"},
)

client_a = OBISClient(
    local_peer_id="peer:a",
    remote_peer_id="peer:b",
    key_id="peer-a-key",
    principal_ref="principal:a",
    secret=secret,
    scopes={"catalog:read"},
)

with OBISServer(peer_b) as server:
    result = client_a.invoke(
        server.address, "catalog.lookup", "1.0", {"item_id": "demo"}
    )
    print(result["result"])
```

The reference server and client deliberately bind to loopback addresses only. This prevents this draft prototype from being mistaken for a production internet-facing service.

## Security limitations — do not deploy for real workloads

The shared-secret HMAC profile is only a local conformance/development mechanism. It does not provide a complete production identity lifecycle, certificate validation, asymmetric signatures, TLS, durable replay storage, distributed revocation, or a formal cryptographic profile. The default in-memory replay guard resets on process restart. Deployments that need restart-persistent replay rejection can inject `SQLiteReplayGuard('/owner-controlled/path/obis-replay.sqlite3')` into `OBISPeer`. The database is local to the Bridge owner; it is not a shared service, distributed revocation mechanism, or production security approval. Backups, filesystem permissions, disk protection, and retention operations remain the Bridge owner's responsibility. Error responses for authentication failures are intentionally not signed.

Before production use, OBIS requires a reviewed security profile covering mutual peer authentication, authenticated encrypted transport, key issuance/storage/rotation/revocation, authorization context binding, durable replay/idempotency, audit integrity, and threat-model validation. The current implementation must not be used for financial, personal, safety-critical, or otherwise sensitive operations.

## Independence check

The package can be installed and tested from this directory alone. It imports only the Python standard library at runtime. Its tests instantiate two peers and exchange messages over loopback HTTP; neither TRADIX nor BRIDEX services are started or contacted.
