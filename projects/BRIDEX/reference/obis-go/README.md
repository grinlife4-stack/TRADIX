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
- In-memory nonce replay rejection by default, with an optional owner-local durable file-backed replay guard.
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

The optional Go `FileReplayGuard` persists nonce claims across process restarts using exclusive file creation, file sync, and directory sync. Configure it before serving with `SetReplayGuard`; the directory must already exist and be controlled by the Bridge owner. Duplicate claims are rejected across guard instances/processes. Storage errors fail closed with HTTP 503 before capability execution. Marker files are intentionally retained permanently to avoid reopening replay windows; this consumes unbounded storage over time and requires owner monitoring/retention planning. This is local durable replay protection, not distributed replay protection or business-operation idempotency/outcome reconciliation. The default remains in-memory for development. The implementation still lacks durable operation idempotency/outcome reconciliation, production audit persistence, and the complete malformed-message/transport failure matrix. The current Go envelope validator is implemented independently and is not yet a full JSON Schema validator for every possible OBIS message.

Do not expose this peer to the public internet or use it for real credentials or business data.


## Durable replay guard

The Go peer offers an opt-in standard-library-only `FileReplayGuard` for owner-local persistence:

```go
guard, err := obis.NewFileReplayGuard("/var/lib/my-bridge/obis-replay")
if err != nil { return err }
if err := peer.SetReplayGuard(guard); err != nil { return err }
```

Create the directory before startup and restrict it to the Bridge owner. Configure the guard before the peer begins serving requests. A nonce claim is created atomically with exclusive file creation; the marker and containing directory are synced before capability execution is allowed. A duplicate is rejected even after constructing a new guard or restarting the process. Any uncertain write/sync failure is fail-closed and prevents the handler from running.

Markers are not automatically deleted, including after request expiry. This deliberately trades storage growth for avoiding unsafe cleanup races and replay-window reopening. Operators must monitor capacity and treat the directory as persistent security state. Do not manually delete markers while the peer is active. This guard is not distributed coordination, an operation idempotency ledger, or a production authentication profile.
