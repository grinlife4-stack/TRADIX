# OBIS Go Reference Peer

Independent Go standard-library implementation of the OBIS 0.1 development/conformance profile.

## Development mode

~~~bash
cd projects/BRIDEX/reference/obis-go
OBIS_TEST_SECRET='replace-with-a-local-test-secret-at-least-32-bytes' go run ./cmd/obis-go-peer
~~~

The listener defaults to 127.0.0.1:18081 and refuses non-loopback bind addresses. The development mode uses HMAC authentication and is loopback-only.

## TLS 1.3 mTLS candidate

The peer can optionally enable TLS when all three variables are supplied:

- OBIS_TLS_CERT: server certificate chain.
- OBIS_TLS_KEY: server private key path, supplied by the owner at runtime.
- OBIS_TLS_CA: CA bundle used to validate client certificates.

Partial TLS configuration fails closed. TLS mode requires TLS 1.3, a verified client certificate, HTTP/1.1 ALPN, and a certificate URI SAN matching the OBIS sender identity.

This Go reference currently combines the TLS transport with the development HMAC application credential. It is not yet equivalent to the Python no-HMAC fingerprint-bound candidate. Do not treat this as a production-approved security profile.

## Tests

~~~bash
go test ./...
~~~

The Python cross-language test runs this peer on loopback and exercises the Go/Python request-response contract. No production endpoint or key is included.
