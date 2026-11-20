# OBIS 0.2 — Operation Identity, Idempotency, and Outcome Recovery

**Status:** Draft extension for review and implementation  
**Protocol version:** `obis/0.2`  
**Compatibility:** OBIS 0.1 is immutable and remains valid for existing synchronous exchanges. A peer MUST NOT silently reinterpret a 0.1 request as 0.2.  
**Canonical schema:** `standards/obis/0.2/message.schema.json`

## 1. Purpose

OBIS 0.2 defines a durable identity for a logical operation across multiple transport attempts. It separates the request message, the logical operation, and each attempt to deliver or recover that operation.

A transport timeout is not evidence that the remote capability did not execute. An implementation MUST preserve that uncertainty instead of translating it into a definite failure or blindly invoking the capability again.

## 2. Four distinct identifiers

| Identifier | Lifetime | Rule |
|---|---|---|
| `message_id` | One OBIS message | Unique for every request or response message |
| `nonce` | One authenticated request attempt | Unique; checked by the replay guard |
| `attempt_id` | One transport attempt | New value for every send/re-send/status query |
| `operation_id` | One logical operation | Stable across retries, status queries, and recovery |

`idempotency_key` is also stable across attempts. It is not a substitute for `operation_id`; it is the caller's deduplication key within a defined authorization scope.

## 3. Request hash

The sender MUST compute SHA-256 over the OBIS 0.2 canonical JSON representation of this exact object:

```json
{
  "protocol": "obis",
  "version": "0.2",
  "sender": {"peer_id": "sender-peer"},
  "recipient": {"peer_id": "receiver-peer"},
  "principal_ref": "principal:caller",
  "scopes": ["capability:execute"],
  "capability": {"id": "records.write", "version": "1.0"},
  "payload": {"record_id": "record-42", "value": "example"}
}
```

The `scopes` array MUST be sorted lexicographically before hashing. The canonicalization profile for this draft is the JSON Canonicalization Scheme (JCS, RFC 8785). The request hash MUST be lowercase hexadecimal SHA-256. The operation metadata, idempotency key, attempt ID, nonce, message ID, and transport timestamps are deliberately excluded from the hash.

The receiver MUST recompute and compare the hash before reserving or executing the operation. A mismatch MUST be rejected.

## 4. Idempotency scope and conflict rules

The receiver MUST scope an idempotency key to the tuple:

`authenticated sender peer + authenticated principal + capability ID + capability version + idempotency_key`

The receiver MUST persist the tuple, operation ID, request hash, operation state, and recoverable result/error in an owner-controlled durable Operation Ledger before invoking a side-effecting handler.

- Same scope, same idempotency key, same operation ID, same request hash: return the existing operation state/result. Do not execute the handler again.
- Same scope and idempotency key with a different operation ID or request hash: reject with `operation.idempotency_conflict`.
- Same operation ID with a different idempotency key, principal, peer, capability, or request hash: reject with `operation.idempotency_conflict`.
- A request received while the existing operation is `ACCEPTED` or `RUNNING` MUST return that state. It MUST NOT start a second handler invocation.
- The receiver MUST NOT use an in-memory-only ledger for OBIS 0.2 operations. If durable storage is unavailable, it MUST fail closed before invoking the capability.

## 5. Operation states

`ACCEPTED → RUNNING → SUCCEEDED | FAILED | UNKNOWN`

Additional terminal states are `REJECTED`, `CANCELLED`, and `EXPIRED`. A capability may expose `ACCEPTED` when it has durably accepted work for later processing. `RUNNING` means execution has started. A terminal state MUST NOT be silently reopened.

- `SUCCEEDED`: a validated result or owner-controlled result reference is durably committed.
- `FAILED`: execution is known to have failed; the failure code is stable and safe to disclose.
- `REJECTED`: the operation was not executed because local authentication, authorization, policy, or validation rejected it.
- `UNKNOWN`: the receiver cannot prove whether the side effect occurred or cannot safely recover its result.
- `CANCELLED`: cancellation is confirmed according to the capability's declared cancellation semantics.
- `EXPIRED`: the operation's declared lifetime elapsed and the owner can prove no further execution will occur. Expiry alone MUST NOT be used to claim that a side effect was rolled back.

On receiver restart, any persisted `RUNNING` operation without a committed terminal result MUST be changed to `UNKNOWN` before new requests are served. It MUST NOT be automatically re-executed.

## 6. Status and result recovery

A sender queries the same receiver with `message_type: operation_status_request`, the original `operation_id`, the original capability identity, and an authenticated principal that is authorized to inspect that operation.

The receiver MUST verify that the authenticated peer, principal, and capability match the ledger record. Knowledge of an operation ID alone MUST NOT grant access.

A status response returns the complete operation record. If state is `SUCCEEDED`, the response MUST contain either the result object or a resolvable owner-controlled `result_ref`. If state is `FAILED` or `REJECTED`, it MUST contain a stable `failure_code`. If state is `UNKNOWN`, result and failure code may be null; the receiver MUST NOT fabricate a result.

Status queries are read-only. They MUST NOT invoke the capability handler or change the operation state.

## 7. Recovery classes

Every side-effecting capability MUST declare one recovery class in its capability metadata:

- `IDEMPOTENT`: the capability's own external operation accepts and enforces the same idempotency key. A retry is permitted only under the capability's explicit policy and with the same operation identity and request hash.
- `QUERYABLE`: the capability can query the external system by a stable external operation reference and reconcile the result without repeating the side effect.
- `NON_RECOVERABLE`: the capability cannot safely determine the outcome after a crash or lost response. The operation remains `UNKNOWN` until an authorized owner/operator resolves it.

The OBIS ledger alone cannot guarantee exactly-once effects in an external provider. A crash can occur after the provider commits a side effect but before the Bridge commits the result. In that case, `UNKNOWN` is the only honest state unless the provider offers idempotency or outcome lookup.

## 8. Operation Ledger minimum record

The owner-local durable ledger MUST persist at least:

- `operation_id`
- idempotency scope and `idempotency_key`
- `request_hash`
- authenticated `peer_id` and `principal_ref`
- `capability_id` and `capability_version`
- `state`
- `result` or `result_ref`
- `failure_code`
- `created_at`, `updated_at`, and `expires_at`

The ledger MUST use atomic reservation so concurrent duplicate requests cannot both start the same operation. The ledger belongs to the Bridge owner exposing the capability. It MUST NOT be centralized in ECOSCAN, BRIDEX, or TRADIX.

## 9. Timeout and retry rules

- Timeout before any request bytes are sent: transport outcome is `NOT_SENT`; the sender may submit the operation using the same operation ID and idempotency key.
- Timeout or connection loss after request transmission may have started: transport outcome is `TRANSPORT_UNKNOWN`; operation state is `UNKNOWN` unless a later authenticated response/status query resolves it.
- A valid operation response is `RESPONSE_RECEIVED`; its operation state is authoritative only after signature/peer/correlation/hash validation.
- The sender MAY retry a status query with a new message ID, nonce, and attempt ID.
- The sender MUST NOT create a new operation ID or a new idempotency key merely because a response was lost.
- The sender MUST NOT blindly repeat the side-effecting handler while the outcome is `UNKNOWN`.

Transport outcome and operation state are independent dimensions and MUST NOT be collapsed into one enum.

## 10. Security, privacy, and retention

Operation status is protected data. The receiver MUST enforce the original peer/principal/capability boundary for every status request. Idempotency keys MUST NOT be treated as secrets or authentication credentials. The ledger SHOULD store a digest of the scoped idempotency key when raw key retention is unnecessary.

The owner defines retention, export, backup, and deletion. A tombstone MUST remain long enough to prevent a late retry from repeating an operation after its result record is removed. Ledger storage failure MUST fail closed for new side-effecting operations.

## 11. Compatibility and migration

OBIS 0.1 remains unchanged. OBIS 0.2 uses a separate versioned message schema and transport path. A receiver may support both versions concurrently, but MUST dispatch by the explicit version/path and MUST NOT downgrade a 0.2 operation to 0.1.

OBIS 0.2 is a draft contract. Production TLS/mTLS, credential lifecycle, signed evidence, distributed replay coordination, and independent security review remain separate release gates.
