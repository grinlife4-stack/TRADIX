"""OBIS 0.2 operation handling for the Python reference peer.

This module is a loopback/development reference. It does not provide production
TLS, peer certificate identity, or external-provider exactly-once guarantees.
"""
from __future__ import annotations

import hashlib
import hmac
import math
import secrets
import time
from dataclasses import dataclass
from typing import Any, Callable

import rfc8785

from .operations import (
    IdempotencyConflict,
    OperationLedger,
    OperationLedgerError,
)
from .peer import (
    CLOCK_SKEW_SECONDS,
    MAX_MESSAGE_BYTES,
    MAX_TTL_SECONDS,
    OBISPeer,
    OBISRequestError,
    canonical_json,
    verify_signature,
)


VERSION = "0.2"


@dataclass(frozen=True)
class OperationCapability:
    capability_id: str
    version: str
    required_scopes: frozenset[str]
    handler: Callable[[dict[str, Any]], dict[str, Any]]
    recovery_class: str
    resource_binding: bool = False


def operation_request_hash(message: dict[str, Any]) -> str:
    """Return SHA-256 over the RFC 8785 canonical operation identity/payload."""
    authorization = message["authorization"]
    hashed = {
        "protocol": "obis",
        "version": "0.2",
        "sender": message["sender"],
        "recipient": message["recipient"],
        "principal_ref": authorization["principal_ref"],
        "scopes": sorted(authorization["scopes"]),
        "capability": message["capability"],
        "payload": message["payload"],
    }
    return hashlib.sha256(rfc8785.dumps(hashed)).hexdigest()


def validate_v02_message(message: Any, now: float | None = None) -> None:
    now = time.time() if now is None else now
    if not isinstance(message, dict):
        raise OBISRequestError("protocol.invalid_message", "message must be an object")
    common = {
        "protocol", "version", "message_type", "message_id", "nonce",
        "attempt_id", "sender", "recipient", "issued_at", "expires_at",
        "capability", "authorization",
    }
    if message.get("protocol") != "obis" or message.get("version") != VERSION:
        raise OBISRequestError("protocol.unsupported_version", "unsupported protocol/version", 426)
    message_type = message.get("message_type")
    required = common | ({"operation", "payload"} if message_type == "request" else {"operation_id"} if message_type == "operation_status_request" else set())
    if not required or set(message) != required:
        raise OBISRequestError("protocol.invalid_message", "unknown or missing OBIS 0.2 fields")
    for field in ("message_id", "nonce", "attempt_id"):
        value = message.get(field)
        if not isinstance(value, str) or not value or len(value) > 200:
            raise OBISRequestError("protocol.invalid_message", f"invalid {field}")
    for field in ("sender", "recipient"):
        value = message.get(field)
        if not isinstance(value, dict) or set(value) != {"peer_id"} or not isinstance(value["peer_id"], str) or not value["peer_id"]:
            raise OBISRequestError("protocol.invalid_message", f"invalid {field}")
    capability = message.get("capability")
    if not isinstance(capability, dict) or set(capability) != {"id", "version"} or not all(isinstance(capability[k], str) and capability[k] for k in ("id", "version")):
        raise OBISRequestError("protocol.invalid_message", "invalid capability")
    auth = message.get("authorization")
    if not isinstance(auth, dict) or set(auth) != {"principal_ref", "scopes"}:
        raise OBISRequestError("protocol.invalid_message", "invalid authorization")
    scopes = auth.get("scopes")
    if not isinstance(auth.get("principal_ref"), str) or not auth["principal_ref"] or not isinstance(scopes, list) or not scopes or any(not isinstance(x, str) or not x for x in scopes) or len(set(scopes)) != len(scopes):
        raise OBISRequestError("protocol.invalid_message", "invalid authorization fields")
    issued_at, expires_at = message.get("issued_at"), message.get("expires_at")
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x < 0 for x in (issued_at, expires_at)):
        raise OBISRequestError("protocol.invalid_message", "timestamps must be finite non-negative numbers")
    if issued_at > now + CLOCK_SKEW_SECONDS or expires_at <= now or expires_at <= issued_at or expires_at - issued_at > MAX_TTL_SECONDS:
        raise OBISRequestError("request.expired", "request is expired or has an invalid TTL", 408)
    if len(canonical_json(message)) > MAX_MESSAGE_BYTES:
        raise OBISRequestError("payload.too_large", "message exceeds size limit", 413)
    if message_type == "request":
        operation = message.get("operation")
        if not isinstance(operation, dict) or set(operation) != {"operation_id", "idempotency_key", "request_hash", "expires_at"}:
            raise OBISRequestError("protocol.invalid_message", "invalid operation identity")
        if any(not isinstance(operation.get(k), str) or not operation[k] for k in ("operation_id", "idempotency_key")):
            raise OBISRequestError("protocol.invalid_message", "invalid operation ID or idempotency key")
        request_hash = operation.get("request_hash")
        if not isinstance(request_hash, str) or len(request_hash) != 64 or any(c not in "0123456789abcdef" for c in request_hash):
            raise OBISRequestError("protocol.invalid_message", "invalid request hash")
        op_expiry = operation.get("expires_at")
        if isinstance(op_expiry, bool) or not isinstance(op_expiry, (int, float)) or not math.isfinite(op_expiry) or op_expiry <= now or op_expiry < expires_at:
            raise OBISRequestError("protocol.invalid_message", "operation expiry must be finite and no earlier than message expiry")
        if not isinstance(message.get("payload"), dict):
            raise OBISRequestError("protocol.invalid_message", "payload must be an object")
    else:
        operation_id = message.get("operation_id")
        if not isinstance(operation_id, str) or not operation_id:
            raise OBISRequestError("protocol.invalid_message", "invalid operation_id")


class OBISPeerV02:
    """Versioned operation endpoint sharing identity and replay policy with an OBISPeer."""

    def __init__(self, peer: OBISPeer, ledger: OperationLedger):
        self.peer = peer
        self.ledger = ledger
        self.capabilities: dict[tuple[str, str], OperationCapability] = {}
        self.ledger.recover_running_as_unknown()

    def register_capability(
        self, capability_id: str, version: str,
        required_scopes: set[str] | frozenset[str],
        handler: Callable[[dict[str, Any]], dict[str, Any]],
        *, recovery_class: str, resource_binding: bool = False,
    ) -> None:
        if not capability_id or not version or not callable(handler):
            raise ValueError("capability ID, version, and handler are required")
        if recovery_class not in {"IDEMPOTENT", "QUERYABLE", "NON_RECOVERABLE"}:
            raise ValueError("recovery_class must be IDEMPOTENT, QUERYABLE, or NON_RECOVERABLE")
        if not isinstance(required_scopes, (set, frozenset)) or not required_scopes or any(not isinstance(x, str) or not x for x in required_scopes):
            raise ValueError("capability requires explicit non-empty scopes")
        key = (capability_id, version)
        if key in self.capabilities:
            raise ValueError("capability already registered")
        self.capabilities[key] = OperationCapability(
            capability_id, version, frozenset(required_scopes), handler,
            recovery_class, resource_binding,
        )

    def _authenticate(self, message: dict[str, Any], key_id: str, signature: str):
        credential = self.peer.credentials.get(key_id)
        if credential is None:
            raise OBISRequestError("identity.unknown_peer", "unknown credential", 401)
        if not verify_signature(message, credential.secret, signature):
            raise OBISRequestError("identity.authentication_failed", "signature verification failed", 401)
        if message["sender"]["peer_id"] != credential.peer_id or message["recipient"]["peer_id"] != self.peer.peer_id:
            raise OBISRequestError("identity.authentication_failed", "peer identity mismatch", 401)
        if message["authorization"]["principal_ref"] != credential.principal_ref:
            raise OBISRequestError("identity.authentication_failed", "principal mismatch", 401)
        try:
            accepted = self.peer.replay_guard.accept(f"{key_id}:{message['nonce']}")
        except Exception as exc:
            raise OBISRequestError("replay.storage_unavailable", "replay protection storage unavailable", 503) from exc
        if not accepted:
            raise OBISRequestError("request.replay_detected", "duplicate nonce", 409)
        return credential

    def _authorize(self, message: dict[str, Any], credential: Any) -> OperationCapability:
        key = (message["capability"]["id"], message["capability"]["version"])
        capability = self.capabilities.get(key)
        if capability is None:
            raise OBISRequestError("capability.unknown", "capability is not registered", 404)
        requested = set(message["authorization"]["scopes"])
        if not capability.required_scopes.issubset(requested) or not requested.issubset(credential.allowed_scopes):
            raise OBISRequestError("authorization.denied", "requested scope exceeds capability or credential grant", 403)
        if capability.resource_binding:
            payload = message.get("payload", {})
            project_id, source_id = payload.get("project_id"), payload.get("source_id")
            if (project_id, source_id) not in credential.allowed_resources:
                raise OBISRequestError("authorization.denied", "resource is outside credential grant", 403)
        return capability

    def _response(self, message: dict[str, Any], operation: dict[str, Any]) -> dict[str, Any]:
        return {
            "protocol": "obis",
            "version": VERSION,
            "message_type": "operation_response",
            "message_id": secrets.token_urlsafe(18),
            "correlation_id": message["message_id"],
            "sender": {"peer_id": self.peer.peer_id},
            "recipient": {"peer_id": message["sender"]["peer_id"]},
            "issued_at": time.time(),
            "operation": {
                "operation_id": operation["operation_id"],
                "request_hash": operation["request_hash"],
                "state": operation["state"],
                "result": operation["result"],
                "result_ref": operation["result_ref"],
                "failure_code": operation["failure_code"],
                "created_at": operation["created_at"],
                "updated_at": operation["updated_at"],
                "expires_at": operation["expires_at"],
            },
        }

    def handle(self, message: dict[str, Any], key_id: str, signature: str) -> tuple[dict[str, Any], bytes]:
        validate_v02_message(message)
        credential = self._authenticate(message, key_id, signature)
        capability = self._authorize(message, credential)
        capability_id, capability_version = capability.capability_id, capability.version
        principal_ref = credential.principal_ref
        if message["message_type"] == "operation_status_request":
            try:
                record = self.ledger.get(
                    message["operation_id"], peer_id=credential.peer_id,
                    principal_ref=principal_ref, capability_id=capability_id,
                    capability_version=capability_version,
                )
            except OperationLedgerError as exc:
                raise OBISRequestError("operation.not_found", "operation not found", 404) from exc
            return self._response(message, record), credential.secret

        expected_hash = operation_request_hash(message)
        operation = message["operation"]
        if not hmac.compare_digest(expected_hash, operation["request_hash"]):
            raise OBISRequestError("operation.request_hash_mismatch", "request hash verification failed", 400)
        try:
            record, created = self.ledger.reserve(
                operation_id=operation["operation_id"],
                idempotency_key=operation["idempotency_key"],
                request_hash=expected_hash,
                peer_id=credential.peer_id,
                principal_ref=principal_ref,
                capability_id=capability_id,
                capability_version=capability_version,
                expires_at=operation["expires_at"],
            )
        except IdempotencyConflict as exc:
            raise OBISRequestError("operation.idempotency_conflict", "idempotency identity conflicts with an existing operation", 409) from exc
        except OperationLedgerError as exc:
            raise OBISRequestError("operation.ledger_unavailable", "operation ledger could not reserve operation", 503) from exc
        if not created:
            return self._response(message, record), credential.secret

        self.ledger.transition(operation["operation_id"], "RUNNING")
        try:
            result = capability.handler(message["payload"])
            if not isinstance(result, dict):
                raise TypeError("capability result must be an object")
            # Ensure result can be represented by the wire format before committing it.
            canonical_json(result)
            record = self.ledger.transition(operation["operation_id"], "SUCCEEDED", result=result)
        except Exception:
            # A handler may have committed an external side effect before raising.
            # Never report definite failure or retry automatically in this case.
            record = self.ledger.transition(
                operation["operation_id"], "UNKNOWN",
                failure_code="operation.outcome_unknown",
            )
        return self._response(message, record), credential.secret
