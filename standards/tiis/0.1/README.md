# TIIS 0.1

This directory contains the canonical, transport-neutral TIIS 0.1 message envelope schema.

- Schema: [message.schema.json](message.schema.json)
- Normative specification: [TIIS Specification](../../../docs/TIIS_SPECIFICATION.md)
- Automated schema tests: [test_tiis_schemas.py](../../../tests/test_tiis_schemas.py)

## Scope

TIIS applies only to authorized communication among TRADIX-internal components. It is not an external protocol and is not required by independent products, external peers, or OBIS Bridges.

## 0.1 limits

The schema validates envelope shape and selected field formats. It does not authenticate a sender, authorize an operation, validate an interface-specific payload, enforce message expiry at runtime, provide durable delivery, or prove a transport secure. Those controls require an implementation and deployment profile with separate tests.

No production authentication profile or runtime transport is approved by this schema release.
