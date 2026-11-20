"""OBIS 0.2 operation handling for the Python reference peer.

This module is a loopback/development reference. It does not provide production
TLS, peer certificate identity, or external-provider exactly-once guarantees.
"""
from __future__ import annotations

import hashlib
import hmac
import http.client
import json
import math
import re
import secrets
import socket
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

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
    MESSAGE_PATH_V02,
    OBISPeer,
    OBISRequestError,
    canonical_json,
    sign_message,
    strict_json_loads,
    verify_signature,
    _deadline_http_exchange,
)


VERSION = "0.2"
_RESOURCE_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_RESOURCE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


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
    if message_type == "operation_status_request" and "resource" in message:
        required.add("resource")
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
        if "resource" in message:
            resource = message["resource"]
            if not isinstance(resource, dict) or set(resource) != {"project_id", "source_id"} or any(not isinstance(resource.get(k), str) or not resource[k] for k in ("project_id", "source_id")):
                raise OBISRequestError("protocol.invalid_message", "invalid resource identity")


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
            payload = message.get("payload", message.get("resource", {}))
            project_id, source_id = payload.get("project_id"), payload.get("source_id")
            if (
                not isinstance(project_id, str)
                or not isinstance(source_id, str)
                or not _RESOURCE_IDENTIFIER.fullmatch(project_id)
                or not _RESOURCE_IDENTIFIER.fullmatch(source_id)
                or (project_id, source_id) not in credential.allowed_resources
            ):
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
        try:
            return self._handle_authenticated(message, credential)
        except OBISRequestError as exc:
            exc.authenticated_credential = credential
            exc.request_message = message
            raise

    def _handle_authenticated(self, message: dict[str, Any], credential: Any) -> tuple[dict[str, Any], bytes]:
        capability = self._authorize(message, credential)
        capability_id, capability_version = capability.capability_id, capability.version
        principal_ref = credential.principal_ref
        resource_ref = ""
        if capability.resource_binding:
            resource_identity = message.get("payload", message.get("resource", {}))
            resource_ref = f"{resource_identity['project_id']}/{resource_identity['source_id']}"
        if message["message_type"] == "operation_status_request":
            try:
                record = self.ledger.get(
                    message["operation_id"], peer_id=credential.peer_id,
                    principal_ref=principal_ref, capability_id=capability_id,
                    capability_version=capability_version,
                    resource_ref=resource_ref,
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
                resource_ref=resource_ref,
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
            canonical_json(result)
            record = self.ledger.transition(operation["operation_id"], "SUCCEEDED", result=result)
        except Exception:
            record = self.ledger.transition(
                operation["operation_id"], "UNKNOWN",
                failure_code="operation.outcome_unknown",
            )
        return self._response(message, record), credential.secret


class OBISV02Server:
    """Loopback-only HTTP binding for the OBIS 0.2 reference peer."""

    def __init__(self, peer: OBISPeerV02, host: str = "127.0.0.1", port: int = 0):
        if host not in ("127.0.0.1", "::1", "localhost"):
            raise ValueError("reference server is loopback-only; production transport is not implemented")
        self.peer = peer
        self.httpd = ThreadingHTTPServer((host, port), self._handler_class())
        self.thread: threading.Thread | None = None

    def _handler_class(self):
        peer = self.peer

        class Handler(BaseHTTPRequestHandler):
            server_version = "OBIS-Reference/0.2"

            def do_POST(self):
                if urlparse(self.path).path != MESSAGE_PATH_V02:
                    self.send_error(404)
                    return
                try:
                    if self.headers.get_content_type() != "application/obis+json":
                        self.send_error(415, "unsupported content type")
                        return
                    if self.headers.get("Transfer-Encoding"):
                        self.send_error(400, "transfer encoding is not supported")
                        return
                    raw_length = self.headers.get("Content-Length", "")
                    if not raw_length.isdigit():
                        self.send_error(400, "content length is required")
                        return
                    length = int(raw_length)
                    if length <= 0 or length > MAX_MESSAGE_BYTES:
                        self.send_error(413)
                        return
                    raw = self.rfile.read(length)
                    message = strict_json_loads(raw.decode("utf-8"))
                    if not isinstance(message, dict):
                        raise OBISRequestError("protocol.invalid_message", "message must be an object")
                    response, secret = peer.handle(
                        message,
                        self.headers.get("X-OBIS-Key-Id", ""),
                        self.headers.get("X-OBIS-Signature", ""),
                    )
                    body = canonical_json(response)
                    signature = hmac.new(secret, body, hashlib.sha256).hexdigest()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/obis+json")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("X-OBIS-Signature", signature)
                    self.end_headers()
                    self.wfile.write(body)
                except OBISRequestError as exc:
                    credential = exc.authenticated_credential
                    request_message = exc.request_message
                    if credential is not None and request_message is not None:
                        sender = request_message["sender"]["peer_id"]
                        error_response = {
                            "protocol": "obis", "version": "0.2", "message_type": "error_response",
                            "message_id": str(uuid.uuid4()), "correlation_id": request_message["message_id"],
                            "sender": {"peer_id": peer.peer.peer_id},
                            "recipient": {"peer_id": sender},
                            "issued_at": time.time(),
                            "error": {"code": exc.code, "message": str(exc)},
                        }
                        body = canonical_json(error_response)
                        response_signature = hmac.new(credential.secret, body, hashlib.sha256).hexdigest()
                        self.send_response(exc.http_status)
                        self.send_header("Content-Type", "application/obis+json")
                        self.send_header("Content-Length", str(len(body)))
                        self.send_header("X-OBIS-Signature", response_signature)
                        self.end_headers()
                        self.wfile.write(body)
                    else:
                        body = canonical_json({"error": {"code": exc.code, "message": str(exc)}})
                        self.send_response(exc.http_status)
                        self.send_header("Content-Type", "application/obis+json")
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
                    self.send_error(400, "invalid JSON message")

            def log_message(self, fmt, *args):
                return

        return Handler

    @property
    def address(self) -> str:
        host, port = self.httpd.server_address[:2]
        return f"http://{host}:{port}"

    def start(self) -> "OBISV02Server":
        if self.thread and self.thread.is_alive():
            return self
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        return self

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        if self.thread:
            self.thread.join(timeout=2)

    def __enter__(self) -> "OBISV02Server":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


class OBISV02Client:
    """Loopback-only OBIS 0.2 client with stable operation identity."""

    def __init__(
        self, local_peer_id: str, remote_peer_id: str, key_id: str,
        principal_ref: str, secret: bytes, scopes: set[str] | frozenset[str],
        timeout: float = 3.0,
    ):
        if not all((local_peer_id, remote_peer_id, key_id, principal_ref)):
            raise ValueError("peer, key, and principal identifiers are required")
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise ValueError("reference-profile secret must contain at least 32 bytes")
        if not isinstance(scopes, (set, frozenset)) or not scopes or any(not isinstance(x, str) or not x for x in scopes):
            raise ValueError("client scopes must be a non-empty set of strings")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be a finite positive number")
        self.local_peer_id = local_peer_id
        self.remote_peer_id = remote_peer_id
        self.key_id = key_id
        self.principal_ref = principal_ref
        self.secret = secret
        self.scopes = frozenset(scopes)
        self.timeout = float(timeout)

    def _base(self, message_type: str, capability_id: str, capability_version: str, now: float) -> dict[str, Any]:
        return {
            "protocol": "obis", "version": VERSION, "message_type": message_type,
            "message_id": secrets.token_urlsafe(18), "nonce": secrets.token_urlsafe(24),
            "attempt_id": secrets.token_urlsafe(18),
            "sender": {"peer_id": self.local_peer_id},
            "recipient": {"peer_id": self.remote_peer_id},
            "issued_at": now, "expires_at": now + MAX_TTL_SECONDS,
            "capability": {"id": capability_id, "version": capability_version},
            "authorization": {"principal_ref": self.principal_ref, "scopes": sorted(self.scopes)},
        }

    def _exchange(self, endpoint: str, message: dict[str, Any]) -> dict[str, Any]:
        parsed = urlparse(endpoint)
        if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "::1", "localhost"):
            raise ValueError("reference client is loopback-only; production transport is not implemented")
        if parsed.username is not None or parsed.password is not None or parsed.path not in ("", "/") or parsed.params or parsed.query or parsed.fragment:
            raise ValueError("endpoint must be a bare loopback base URL")
        body = canonical_json(message)
        headers = {
            "Content-Type": "application/obis+json",
            "X-OBIS-Key-Id": self.key_id,
            "X-OBIS-Signature": sign_message(message, self.secret),
        }
        try:
            status, response_headers, response_body = _deadline_http_exchange(
                endpoint, body, headers, time.monotonic() + self.timeout,
                message_path=MESSAGE_PATH_V02,
            )
        except (TimeoutError, socket.timeout) as exc:
            raise OBISRequestError("peer.timeout", "OBIS 0.2 peer request timed out", 504) from exc
        except (OSError, http.client.HTTPException) as exc:
            raise OBISRequestError("peer.unavailable", "OBIS 0.2 peer is unavailable", 503) from exc
        if status != 200:
            signature = response_headers.get("X-OBIS-Signature", "")
            if signature:
                try:
                    error_response = strict_json_loads(response_body.decode("utf-8"))
                    if not isinstance(error_response, dict) or not verify_signature(error_response, self.secret, signature):
                        raise OBISRequestError("identity.authentication_failed", "signed error response verification failed", 502)
                    required_error = {
                        "protocol", "version", "message_type", "message_id", "correlation_id",
                        "sender", "recipient", "issued_at", "error",
                    }
                    if set(error_response) != required_error or error_response.get("protocol") != "obis" or error_response.get("version") != VERSION or error_response.get("message_type") != "error_response":
                        raise OBISRequestError("protocol.invalid_message", "invalid signed error response", 502)
                    if error_response.get("correlation_id") != message["message_id"]:
                        raise OBISRequestError("protocol.invalid_message", "signed error correlation mismatch", 502)
                    sender = error_response.get("sender")
                    recipient = error_response.get("recipient")
                    if not isinstance(sender, dict) or sender.get("peer_id") != self.remote_peer_id or not isinstance(recipient, dict) or recipient.get("peer_id") != self.local_peer_id:
                        raise OBISRequestError("identity.authentication_failed", "signed error peer identity mismatch", 502)
                    error = error_response.get("error")
                    if not isinstance(error, dict) or set(error) != {"code", "message"} or not all(isinstance(error.get(k), str) and error[k] for k in ("code", "message")):
                        raise OBISRequestError("protocol.invalid_message", "invalid signed error details", 502)
                    raise OBISRequestError(error["code"], error["message"], status)
                except OBISRequestError:
                    raise
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError, RecursionError) as exc:
                    raise OBISRequestError("protocol.invalid_message", "invalid signed error response", 502) from exc
            detail = response_body.decode("utf-8", errors="replace")[:512]
            raise OBISRequestError("peer.request_rejected", f"OBIS 0.2 peer returned HTTP {status}: {detail}", status)
        if len(response_body) > MAX_MESSAGE_BYTES:
            raise OBISRequestError("payload.too_large", "response exceeds size limit", 502)
        try:
            response = strict_json_loads(response_body.decode("utf-8"))
            signature = response_headers.get("X-OBIS-Signature", "")
            if not isinstance(response, dict) or not verify_signature(response, self.secret, signature):
                raise OBISRequestError("identity.authentication_failed", "response signature verification failed", 502)
        except OBISRequestError:
            raise
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError, TypeError) as exc:
            raise OBISRequestError("protocol.invalid_message", "invalid signed response", 502) from exc
        required = {
            "protocol", "version", "message_type", "message_id", "correlation_id",
            "sender", "recipient", "issued_at", "operation",
        }
        if set(response) != required or response.get("protocol") != "obis" or response.get("version") != VERSION or response.get("message_type") != "operation_response":
            raise OBISRequestError("protocol.invalid_message", "unexpected OBIS 0.2 response envelope", 502)
        if response.get("correlation_id") != message["message_id"]:
            raise OBISRequestError("protocol.invalid_message", "response correlation mismatch", 502)
        if response.get("sender") != {"peer_id": self.remote_peer_id} or response.get("recipient") != {"peer_id": self.local_peer_id}:
            raise OBISRequestError("identity.authentication_failed", "response peer identity mismatch", 502)
        op = response.get("operation")
        op_fields = {"operation_id", "request_hash", "state", "result", "result_ref", "failure_code", "created_at", "updated_at", "expires_at"}
        if not isinstance(op, dict) or set(op) != op_fields:
            raise OBISRequestError("protocol.invalid_message", "invalid operation response record", 502)
        if op["state"] not in {"ACCEPTED", "RUNNING", "SUCCEEDED", "FAILED", "REJECTED", "UNKNOWN", "CANCELLED", "EXPIRED"}:
            raise OBISRequestError("protocol.invalid_message", "invalid operation state", 502)
        if message["message_type"] == "request":
            if op["operation_id"] != message["operation"]["operation_id"] or op["request_hash"] != message["operation"]["request_hash"]:
                raise OBISRequestError("protocol.invalid_message", "operation identity/hash mismatch", 502)
        return response

    def invoke(
        self, endpoint: str, capability_id: str, capability_version: str,
        payload: dict[str, Any], *, operation_id: str, idempotency_key: str,
        operation_ttl: int = 300,
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        if not isinstance(operation_ttl, int) or isinstance(operation_ttl, bool) or operation_ttl <= MAX_TTL_SECONDS:
            raise ValueError("operation_ttl must be an integer greater than the message TTL")
        now = time.time()
        message = self._base("request", capability_id, capability_version, now)
        message["operation"] = {
            "operation_id": operation_id,
            "idempotency_key": idempotency_key,
            "request_hash": "",
            "expires_at": now + operation_ttl,
        }
        message["payload"] = payload
        message["operation"]["request_hash"] = operation_request_hash(message)
        return self._exchange(endpoint, message)

    def status(
        self, endpoint: str, capability_id: str, capability_version: str,
        operation_id: str, *, resource: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        message = self._base("operation_status_request", capability_id, capability_version, time.time())
        message["operation_id"] = operation_id
        if resource is not None:
            message["resource"] = resource
        return self._exchange(endpoint, message)
