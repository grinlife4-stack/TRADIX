# OBIS 0.1 Conformance Vectors

This directory contains language-neutral message-schema vectors for OBIS 0.1.

## Files

- `vectors.json`: versioned suite with expected accept/reject results and complete message objects.
- `suite.schema.json`: schema for the vector-suite envelope.
- `../message.schema.json`: canonical OBIS 0.1 wire-message schema.

## Run with BRIDEX Core

From the repository root, after installing BRIDEX Core:

```bash
bridex-manifest conformance schema standards/obis/0.1/conformance/vectors.json
```

The suite currently contains three accepted and four rejected messages. A runner must report a mismatch if a message's actual schema-validation result differs from its expected result.

## Scope boundary

These vectors test only the published JSON message schema. They do not test:
- Authentication or a production TLS/mTLS profile.
- Capability authorization or credential-to-peer mapping.
- Request/response correlation semantics beyond schema shape.
- Replay, idempotency, retries, or unknown operation outcomes.
- Transport behavior or a running peer.

A second-language implementation can consume these exact vectors without importing Python code. Runtime peer interoperability requires a separate behavior/transport suite and remains a later acceptance gate. The vectors do not turn the development-only HMAC profile into a normative or production security profile.
