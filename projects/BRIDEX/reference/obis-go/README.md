# OBIS Go Reference Peer

Independent Go standard-library reference peer for OBIS 0.1.

## Development mode

~~~bash
cd projects/BRIDEX/reference/obis-go
OBIS_TEST_SECRET='replace-with-a-local-test-secret-at-least-32-bytes' go run ./cmd/obis-go-peer
~~~

The listener defaults to 127.0.0.1:18081 and refuses non-loopback bind addresses. This mode uses the shared-secret HMAC development profile only.

## TLS 1.3 mutual-authentication candidate

Set all three variables to enable HTTPS with mandatory client certificate verification:

- OBIS_TLS_CERT: server certificate chain.
- OBIS_TLS_KEY: server private key path, supplied by the Bridge owner at runtime.
- OBIS_TLS_CA: CA bundle used to validate client certificates.

Partial TLS configuration fails closed. The listener remains loopback-only. The server requires TLS 1.3, ALPN obis/1, a valid client certificate, and exactly one URI SAN of the form urn:obis:peer:<peer-id>. That peer ID must match the OBIS sender field and the configured credential peer.

The TLS candidate does not implement certificate issuance, rotation, revocation, trust-bundle refresh, or emergency denylisting. The HMAC application authentication remains a development-profile requirement in this reference. Do not use it for production workloads.

## Tests

~~~bash
go test ./...
~~~

The repository's Python cross-language test starts this peer and exercises both HTTP/HMAC and TLS 1.3 mTLS request/response against the Python reference client. Test certificates are generated ephemerally and are not committed.
