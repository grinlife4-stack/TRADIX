# Standalone OBIS Python Reference Peer

This is a small, independently installable reference implementation for the OBIS 0.1 draft. It is intentionally located outside the TRADIX runtime package and has **no runtime dependency on TRADIX or BRIDEX**.

## What is executable
The canonical draft schema is published independently at [standards/obis/0.1/message.schema.json](../../../../standards/obis/0.1/message.schema.json). The Python package includes a byte-identical copy for offline installation; CI checks that they do not drift.


- Direct HTTP request/response between two separately instantiated peers.
- Version and message validation.
- Peer/principal binding to an explicitly configured credential.
- HMAC-SHA256 message and response integrity for the local conformance profile.
- Explicit capability registration and least-privilege scope checks.
- Expiry, maximum TTL, payload-size limits, and in-memory nonce replay rejection.
- Correlated and signed responses.
- Negative tests for spoofing, unknown credentials, excess scopes, replay, expiry, unsupported versions, unknown capabilities, and oversized payloads.

## Run locally

Requires Python 3.11 or newer. No runtime dependencies are required.

```bash
cd projects/BRIDEX/reference/obis-python
python -m pip install -e ".[dev]"
python -m pytest -q
```

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

The shared-secret HMAC profile is only a local conformance/development mechanism. It does not provide a complete production identity lifecycle, certificate validation, asymmetric signatures, TLS, durable replay storage, distributed revocation, or a formal cryptographic profile. The in-memory replay guard resets on process restart. Error responses for authentication failures are intentionally not signed.

Before production use, OBIS requires a reviewed security profile covering mutual peer authentication, authenticated encrypted transport, key issuance/storage/rotation/revocation, authorization context binding, durable replay/idempotency, audit integrity, and threat-model validation. The current implementation must not be used for financial, personal, safety-critical, or otherwise sensitive operations.

## Independence check

The package can be installed and tested from this directory alone. It imports only the Python standard library at runtime. Its tests instantiate two peers and exchange messages over loopback HTTP; neither TRADIX nor BRIDEX services are started or contacted.
