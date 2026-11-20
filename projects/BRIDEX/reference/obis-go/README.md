# OBIS Go Reference Peer

Independent Go standard-library implementation of the OBIS 0.1 development and TLS 1.3 mTLS candidate profiles.

## Development profile

~~~bash
cd projects/BRIDEX/reference/obis-go
OBIS_TEST_SECRET='replace-with-a-local-test-secret-at-least-32-bytes' go run ./cmd/obis-go-peer
~~~

The listener defaults to 127.0.0.1:18081 and refuses non-loopback bind addresses. The HTTP/HMAC development profile is loopback-only.

## TLS 1.3 mTLS candidate

Configure all three server variables to enable HTTPS with mandatory client certificate verification:

- OBIS_TLS_CERT: server certificate chain.
- OBIS_TLS_KEY: server private key path, supplied by the owner at runtime.
- OBIS_TLS_CA: CA bundle used to validate client certificates.

The mTLS profile requires TLS 1.3, HTTP/1.1 ALPN, a canonical URI SAN of the form `urn:obis:peer:<lowercase-UUID>`, and a local credential record binding the client certificate URI and SHA-256 fingerprint to one peer/principal/scope grant. The server certificate URI is checked against its configured peer ID. The Go client verifies its own certificate URI before sending and verifies the remote server certificate URI and endpoint hostname before accepting the connection.

mTLS credentials carry no HMAC shared secret. The TLS channel provides transport confidentiality and integrity; no detached signature or non-repudiation claim is made. The HMAC profile remains separate, loopback-only development functionality.

The certificate issuance, rotation, trust-bundle distribution, durable revocation, CRL/OCSP, emergency response, and production key custody lifecycle remain owner-controlled and unimplemented here. This is a candidate reference profile, not production approval.

## Tests

~~~bash
go test ./...
~~~

The Python cross-language suite exercises HMAC development interoperability and bidirectional Go/Python mTLS request/response using ephemeral test certificates. No production endpoint or private key is included.
