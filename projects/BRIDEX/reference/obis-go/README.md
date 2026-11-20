# OBIS Go Peer

**Status:** independent second-language development peer, early interoperability stage  
**Language:** Go 1.23+  
**Dependencies:** Go standard library only  
**Transport:** direct loopback HTTP binding for local conformance tests  
**Security:** shared-secret HMAC is development/conformance-only; not production security

## Purpose

This package is a separately buildable Go implementation of the OBIS 0.1 request/response path. It does not import, invoke, or depend on the Python reference peer, BRIDEX Core, or any TRADIX runtime service.

It currently provides:
- Strict JSON parsing with duplicate-key and trailing-value rejection.
- OBIS 0.1 request envelope validation, bounded TTL, and message-size checks.
- Explicit peer/principal credential mapping.
- Per-capability scope checks with default-deny behavior.
- In-memory nonce replay rejection.
- Direct loopback HTTP request handling at `/obis/v0.1/messages`.
- A direct Go client with response-signature, correlation, peer-identity, and result validation.
- HMAC-authenticated success responses compatible with the Python development client.\n- A Go client that can invoke the Python reference peer over the same local development profile.
- Tests consuming the shared published OBIS request vectors.

## Run independently

From this directory:

```bash
go test ./...
go build -o obis-go-peer ./cmd/obis-go-peer

./obis-go-peer \
  --peer-id=peer:go \
  --listen=127.0.0.1:8080 \
  --key-id=python-dev-key \
  --remote-peer=peer:python \
  --principal=principal:python \
  --secret-hex=<64-hex-character-development-secret> \
  --scopes=records:read
```

The server prints its bound address on startup. The sample capability is `records.read@1.0`. The `invoke` mode can call a configured Python peer directly:

```bash
./obis-go-peer --mode invoke \\
  --endpoint=http://127.0.0.1:8081 \\
  --peer-id=peer:go --remote-peer=peer:python \\
  --key-id=go-key --principal=principal:go \\
  --secret-hex=<64-hex-character-development-secret> \\
  --scopes=records:read --capability=records.read \\
  --capability-version=1.0 --payload-json='{"record_id":"record-123"}'
```

## Security and conformance boundary

The HMAC profile reproduces the existing Python prototype's local development behavior. It is not a normative production security profile, certificate identity mapping, TLS/mTLS, key lifecycle, or a substitute for the unresolved OBIS security decisions. The server refuses non-loopback listen addresses.

The shared integration tests exercise both directions: Python client → Go server and Go client → Python server. They verify correlated, HMAC-authenticated success responses using the development-only profile. They do not prove authenticated error-response parity, production TLS/mTLS interoperability, durable replay/idempotency, audit persistence, or full OBIS Core Conformance.

Do not expose this peer to the public internet or use it for real credentials or business data.
