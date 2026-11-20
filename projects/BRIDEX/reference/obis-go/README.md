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
- HMAC-authenticated success responses compatible with the Python development client.
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

The server prints its bound address on startup. The sample capability is `records.read@1.0`.

## Security and conformance boundary

The HMAC profile reproduces the existing Python prototype's local development behavior. It is not a normative production security profile, certificate identity mapping, TLS/mTLS, key lifecycle, or a substitute for the unresolved OBIS security decisions. The server refuses non-loopback listen addresses.

The current shared test proves that the Python reference client can send a request to the independent Go server and verify its correlated signed response. It does not yet prove the reverse direction, authenticated error-response parity, production TLS/mTLS interoperability, durable replay/idempotency, audit persistence, or full OBIS Core Conformance.

Do not expose this peer to the public internet or use it for real credentials or business data.
