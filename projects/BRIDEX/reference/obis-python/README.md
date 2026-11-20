# Standalone OBIS Python Reference Peer

This is a small, independently installable reference implementation for the OBIS 0.1 draft. It is intentionally located outside the TRADIX runtime package and has **no runtime dependency on TRADIX or BRIDEX**.

## What is executable
The canonical draft schema is published independently at [standards/http/1.1/message.schema.json](../../../../standards/http/1.1/message.schema.json). The Python package includes a byte-identical copy for offline installation; CI checks that they do not drift.


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

## TLS 1.3 mutual-TLS candidate

A separate `OBIS-TLS-MTLS-1` candidate transport is now available in the Python reference:

- TLS 1.3 only; the client requires certificate-chain and endpoint hostname verification.
- The server requires a client certificate.
- Both sides negotiate ALPN `http/1.1`.
- The server certificate must contain exactly one canonical URI SAN of the form `urn:obis:peer:<lowercase-UUID>`; the client checks it against the configured remote peer ID.
- The client certificate must contain the same URI SAN form; the server binds its URI and SHA-256 certificate fingerprint to one explicit local credential/principal record.
- mTLS credentials carry no HMAC shared secret. The TLS channel protects the response; this does not create a portable detached signature.
- TLS handshake and HTTP request timeouts are bounded. Local credential revocation blocks subsequent requests in that running process.

The owner supplies the SSL contexts, trust anchors, certificate chain, and private-key paths. The package does not create a CA, issue or rotate certificates, distribute trust bundles, or implement CRL/OCSP. The mTLS mode is a reference candidate, not a production-approved security profile. The HMAC example below remains development-only and loopback-only.

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

The HMAC profile remains a local conformance/development mechanism and must not be used beyond loopback. The TLS 1.3 mTLS mode is a candidate reference implementation, not production approval. It does not provide automated CA operations, trust-bundle distribution, certificate renewal, CRL/OCSP, durable revocation, durable replay/idempotency, production audit, or cross-language conformance. The in-memory replay guard and local credential revocation state reset on process restart.

Before production use, OBIS still requires an owner-approved trust model, certificate lifecycle and revocation process, durable replay/idempotency, audit integrity, a second independent language implementation, cross-implementation tests, and independent security review. The current implementation must not be used for financial, personal, safety-critical, or otherwise sensitive operations.

## Independence check

The package can be installed and tested from this directory alone. It imports only the Python standard library at runtime. Its tests instantiate two peers and exchange messages over loopback HTTP; neither TRADIX nor BRIDEX services are started or contacted.
