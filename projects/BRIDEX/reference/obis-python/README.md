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

## TLS 1.3 mutual-authentication candidate

The Python reference client/server and the Go reference server now include an opt-in TLS 1.3 mTLS transport candidate:

- TLS 1.3 only; TLS 1.2 and plaintext fallback are not accepted by the TLS-enabled listener.
- Both peers validate certificates against an owner-supplied trust CA.
- The Go server requires a client certificate and checks that its single OBIS URI SAN is exactly of the form urn:obis:peer:<peer-id>, matching the authenticated OBIS sender.
- The Python client validates the server certificate and hostname and supplies its own client certificate.
- ALPN is fixed to obis/1.
- The reference listener remains loopback-only.

Python setup uses create_tls13_client_context(...) and create_tls13_server_context(...). The Go reference server enables TLS when OBIS_TLS_CERT, OBIS_TLS_KEY, and OBIS_TLS_CA are all supplied; partial configuration fails closed. The Python-to-Go test generates short-lived test certificates at runtime and exercises a real mTLS request/response.

This is a tested candidate transport profile, not production approval. Certificate issuance, rotation, revocation, trust-bundle freshness, emergency denylisting, operational key custody, independent security review, and removal/replacement of the HMAC development authentication layer remain open.

## Security limitations — do not deploy for real workloads

The shared-secret HMAC profile is only a local conformance/development mechanism. It does not provide a complete production identity lifecycle, certificate validation, asymmetric signatures, TLS, durable replay storage, distributed revocation, or a formal cryptographic profile. The in-memory replay guard resets on process restart. Error responses for authentication failures are intentionally not signed.

Before production use, OBIS requires a reviewed security profile covering mutual peer authentication, authenticated encrypted transport, key issuance/storage/rotation/revocation, authorization context binding, durable replay/idempotency, audit integrity, and threat-model validation. The current implementation must not be used for financial, personal, safety-critical, or otherwise sensitive operations.

## Independence check

The package can be installed and tested from this directory alone. It imports only the Python standard library at runtime. Its tests instantiate two peers and exchange messages over loopback HTTP; neither TRADIX nor BRIDEX services are started or contacted.
