# TIIS Integration with TRADIX Tooling Components

**Status:** Local adapter prototypes; no transport or production authentication profile enabled.

## Boundary

TIIS is the internal component-message envelope. It does not merge component ownership, databases, credentials, or lifecycle authority. Each component remains independently operable and may expose a TIIS adapter without requiring a central runtime.

The public Artifact Gateway HTTP API is not replaced by TIIS. External clients continue to use the Gateway's own project-scoped authentication boundary. TIIS is used only by explicitly authorized TRADIX-internal callers.

## Implemented local adapters

### Artifact Gateway

- Interface: `artifact.receipt@0.1.0`
- Operation: `read`
- Read-only, project-bound to the Gateway instance configuration.
- Returns receipt metadata and a small extraction summary.
- Never returns extracted text, ZIP member listings, or artifact bytes.
- Rejects symlink receipts, path-shaped IDs, cross-project records, oversized/corrupt receipt files, and malformed integrity metadata.
- Does not fetch remote S3/GitHub object bytes or claim that the referenced object is currently reachable.

### Tool Catalog

- Interface: `tool.catalog@0.1.0`
- Read operations: `get`, `list`, `history`.
- Uses the existing ToolCatalog public methods; it does not query SQLite tables directly.
- Mutating operations (`register`, `transition`) are intentionally rejected.
- Mutations remain disabled until request idempotency is persisted transactionally and actor/audit semantics are strengthened. A TIIS idempotency key without durable deduplication is not sufficient.

### Tool Adapter Contract

- Interface: `tool.adapter@0.1.0`
- Request operation: `invoke`.
- Event: `tool.adapter.result`.
- Codec maps the existing ToolInvocation, ResourceLimits, and AdapterResult contracts to/from TIIS.
- It enforces the existing job-type allowlist and source-commit binding.
- It does not execute a job, create a worker, invoke a shell, create a sandbox, schedule, or cancel anything.
- Raw adapter error text is not copied into TIIS result events; normalized error codes and evidence references remain the safe reporting surface.

## Authorization

Every inbound adapter requires TIISValidator with a caller-supplied authorization policy. Missing policy is deny. The authenticated component identity is supplied separately from the message and must match the claimed sender. Each adapter also enforces its own recipient/interface/version boundary.

No production authentication profile, credential issuance/rotation, replay store, durable event inbox/outbox, or signed audit store is included. Local adapter tests prove contract behavior only; they do not prove secure network interoperability.

## Next acceptance gates

1. Select and review a production TIIS authentication profile for each deployment class.
2. Add replay protection and durable idempotency before enabling catalog writes or other state-changing operations.
3. Define durable event delivery, retry, acknowledgment, and audit retention.
4. Add independent interface payload schemas and version compatibility tests.
5. Implement the runner/sandbox separately before any Tool Adapter execution path is enabled.
6. Run cross-component integration tests using the actual component implementations and their own isolated data stores.
7. Complete security review and failure-injection tests before any live endpoint is enabled.

Passing these local adapter tests does not authorize a live endpoint, external connection, deployment, or production operation.
