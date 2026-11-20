# OBIS Go Peer

**Status:** independent second-language development peer, early interoperability stage  
**Language:** Go 1.23+  
**Dependencies:** Go standard library only  
**Transport:** direct loopback HTTP for local conformance tests  
**Security:** shared-secret HMAC is development/conformance-only, not production security

## Purpose

This package is a separately buildable Go implementation of the OBIS 0.1 request/response path. It does not import, invoke, or depend on the Python reference peer, BRIDEX Core, or any TRADIX runtime service.

It currently provides:
- Strict JSON parsing with duplicate-key and trailing-value rejection.
- OBIS 0.1 request envelope validation, bounded TTL, and message-size checks.
- Explicit peer/principal credential mapping.
- Per-capability scope checks with default-deny behavior.
- In-memory nonce replay rejection.
- Direct loopback HTTP request handling at /obis/v0.1/messages.
- A Go client that validates response signatures, correlation, peer identity, success envelopes, and signed error envelopes.
- HMAC-authenticated success and correlated error responses compatible with the Python development client.
- Go unit tests over the shared OBIS request and response vectors.

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

The server prints its bound address on startup. Its sample capability is records.read@1.0.

The invoke mode calls a configured Python peer directly:

```bash
./obis-go-peer invoke \
  --endpoint=http://127.0.0.1:8081 \
  --local-peer=peer:go \
  --remote-peer=peer:python \
  --key-id=go-key \
  --principal=principal:go \
  --secret-hex=<64-hex-character-development-secret> \
  --scopes=records:read \
  --capability=records.read \
  --capability-version=1.0 \
  --payload='{"record_id":"record-123"}'
```

## Interoperability evidence

The shared Python integration tests exercise both directions:
- Python client → Go server: authenticated success and correlated capability.unknown / authorization.denied errors.
- Go client → Python server: authenticated success and correlated capability.unknown / authorization.denied errors.

The Go unit tests also consume all published OBIS 0.1 request and response schema vectors. These checks are still an early conformance slice, not a complete cross-language protocol matrix.

## Security and conformance boundary

The HMAC profile reproduces the Python prototype's local development behavior. It is not a normative production security profile, certificate identity mapping, TLS/mTLS, key lifecycle, or a substitute for the unresolved OBIS security decisions. The server and client refuse non-loopback endpoints.

The implementation still lacks distributed replay protection, durable operation idempotency/outcome reconciliation, production audit persistence, and the complete malformed-message/transport failure matrix. The current Go envelope validator is implemented independently and is not yet a full JSON Schema validator for every possible OBIS message.

Do not expose this peer to the public internet or use it for real credentials or business data.
