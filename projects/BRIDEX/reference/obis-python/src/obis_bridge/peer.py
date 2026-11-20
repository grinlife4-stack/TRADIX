"""Minimal, standalone OBIS 0.1 reference peer.

Security note:
The HMAC shared-secret profile here is a deterministic conformance/development
profile only. It is NOT a production identity, key-management, or transport
security solution. Production deployments require an approved security profile
and authenticated encrypted transport.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import secrets
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import urlparse


PROTOCOL = "obis"
VERSION = "0.1"
MESSAGE_PATH = "/obis/v0.1/messages"
MAX_MESSAGE_BYTES = 64 * 1024
MAX_TTL_SECONDS = 60
CLOCK_SKEW_SECONDS = 30


class OBISRequestError(Exception):
    """A remote request failed with a normalized OBIS error."""

    def __init__(
        self, code: str, message: str, http_status: int = 400,
        authenticated_credential: Any = None, request_message: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.http_status = http_status
        self.authenticated_credential = authenticated_credential
        self.request_message = request_message


@dataclass(frozen=True)
class Credential:
    """One explicitly configured peer/principal relationship."""

    key_id: str
    peer_id: str
    principal_ref: str
    secret: bytes = field(repr=False)
    allowed_scopes: frozenset[str]
    allowed_resources: frozenset[tuple[str, str]] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.key_id or not self.peer_id or not self.principal_ref:
            raise ValueError("credential identifiers must be non-empty")
        if not isinstance(self.secret, bytes) or len(self.secret) < 32:
            raise ValueError("reference-profile secret must be bytes of at least 32 bytes")
        if not self.allowed_scopes or not all(isinstance(s, str) and s for s in self.allowed_scopes):
            raise ValueError("credential must have explicit non-empty string scopes")
        object.__setattr__(self, "allowed_scopes", frozenset(self.allowed_scopes))
        resources = frozenset(self.allowed_resources)
        if any(
            not isinstance(pair, tuple) or len(pair) != 2
            or not all(isinstance(value, str) and value for value in pair)
            for pair in resources
        ):
            raise ValueError("allowed_resources must contain project/source identifier pairs")
        object.__setattr__(self, "allowed_resources", resources)


@dataclass(frozen=True)
class Capability:
    capability_id: str
    version: str
    required_scopes: frozenset[str]
    handler: Callable[[dict[str, Any]], dict[str, Any]]
    resource_binding: bool = False


@dataclass
class ReplayGuard:
    """Bounded in-memory replay protection for a single running peer."""

    retention_seconds: int = MAX_TTL_SECONDS + CLOCK_SKEW_SECONDS
    _seen: dict[str, float] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def accept(self, nonce: str, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        with self._lock:
            expired = [key for key, until in self._seen.items() if until <= now]
            for key in expired:
                del self._seen[key]
            if not nonce or nonce in self._seen:
                return False
            self._seen[nonce] = now + self.retention_seconds
            return True


def strict_json_loads(raw: str) -> Any:
    """Parse JSON while rejecting duplicate object keys."""
    def reject_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON object key")
            result[key] = value
        return result

    return json.loads(raw, object_pairs_hook=reject_duplicates)


def canonical_json(value: Any) -> bytes:
    """Stable JSON bytes used for message authentication in this prototype."""
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sign_message(message: dict[str, Any], secret: bytes) -> str:
    return hmac.new(secret, canonical_json(message), hashlib.sha256).hexdigest()


def verify_signature(message: dict[str, Any], secret: bytes, signature: str) -> bool:
    expected = sign_message(message, secret)
    return hmac.compare_digest(expected, signature)


def _required(mapping: dict[str, Any], key: str, expected_type: type) -> Any:
    value = mapping.get(key)
    if not isinstance(value, expected_type):
        raise OBISRequestError("protocol.invalid_message", f"invalid or missing {key}")
    return value


def validate_response(
    message: Any,
    request_message: dict[str, Any],
    local_peer_id: str,
    remote_peer_id: str,
    expected_outcome: str,
) -> None:
    """Validate an authenticated response envelope before exposing it to callers."""
    if not isinstance(message, dict):
        raise OBISRequestError("protocol.invalid_message", "response must be a JSON object", 502)
    common_fields = {
        "protocol", "version", "message_type", "message_id", "correlation_id",
        "sender", "recipient", "issued_at", "outcome",
    }
    outcome_field = "result" if expected_outcome == "succeeded" else "error"
    if set(message) != common_fields | {outcome_field}:
        raise OBISRequestError("protocol.invalid_message", "response has unknown or missing fields", 502)
    if message.get("protocol") != PROTOCOL or message.get("version") != VERSION:
        raise OBISRequestError("protocol.unsupported_version", "unsupported response protocol/version", 502)
    if message.get("message_type") != "response" or message.get("outcome") != expected_outcome:
        raise OBISRequestError("protocol.invalid_message", "unexpected response type or outcome", 502)
    for key in ("message_id", "correlation_id"):
        value = message.get(key)
        if not isinstance(value, str) or not value or len(value) > 200:
            raise OBISRequestError("protocol.invalid_message", f"invalid response {key}", 502)
    if message["correlation_id"] != request_message.get("message_id"):
        raise OBISRequestError("protocol.invalid_message", "response correlation mismatch", 502)
    for key, expected_peer in (("sender", remote_peer_id), ("recipient", local_peer_id)):
        peer_ref = message.get(key)
        if not isinstance(peer_ref, dict) or set(peer_ref) != {"peer_id"}:
            raise OBISRequestError("protocol.invalid_message", f"invalid response {key} reference", 502)
        if peer_ref.get("peer_id") != expected_peer:
            raise OBISRequestError("identity.authentication_failed", f"response {key} peer mismatch", 502)
    issued_at = message.get("issued_at")
    if isinstance(issued_at, bool) or not isinstance(issued_at, (int, float)):
        raise OBISRequestError("protocol.invalid_message", "invalid response timestamp", 502)
    try:
        timestamp_is_valid = math.isfinite(issued_at) and issued_at >= 0
    except (OverflowError, TypeError):
        timestamp_is_valid = False
    if not timestamp_is_valid:
        raise OBISRequestError("protocol.invalid_message", "invalid response timestamp", 502)
    if expected_outcome == "succeeded":
        if not isinstance(message.get("result"), dict):
            raise OBISRequestError("protocol.invalid_message", "success response result must be an object", 502)
    else:
        error = message.get("error")
        if not isinstance(error, dict) or set(error) != {"code", "message"}:
            raise OBISRequestError("protocol.invalid_message", "invalid structured error response", 502)
        if not all(isinstance(error.get(key), str) and error[key] for key in ("code", "message")):
            raise OBISRequestError("protocol.invalid_message", "invalid structured error fields", 502)


def validate_request(message: dict[str, Any], now: float | None = None) -> None:
    now = time.time() if now is None else now
    if not isinstance(message, dict):
        raise OBISRequestError("protocol.invalid_message", "message must be an object")
    if message.get("protocol") != PROTOCOL or message.get("version") != VERSION:
        raise OBISRequestError("protocol.unsupported_version", "unsupported protocol/version", 426)
    if message.get("message_type") != "request":
        raise OBISRequestError("protocol.invalid_message", "message_type must be request")
    allowed_top_level = {
        "protocol", "version", "message_type", "message_id", "nonce", "sender",
        "recipient", "issued_at", "expires_at", "capability", "authorization", "payload",
    }
    if set(message) != allowed_top_level:
        raise OBISRequestError("protocol.invalid_message", "unknown or missing top-level fields")

    for key in ("message_id", "nonce"):
        value = _required(message, key, str)
        if not value or len(value) > 200:
            raise OBISRequestError("protocol.invalid_message", f"invalid {key}")

    sender = _required(message, "sender", dict)
    recipient = _required(message, "recipient", dict)
    auth = _required(message, "authorization", dict)
    capability = _required(message, "capability", dict)
    if set(sender) != {"peer_id"} or set(recipient) != {"peer_id"}:
        raise OBISRequestError("protocol.invalid_message", "peer references contain unknown fields")
    if set(auth) != {"principal_ref", "scopes"} or set(capability) != {"id", "version"}:
        raise OBISRequestError("protocol.invalid_message", "authorization/capability contains unknown fields")
    _required(sender, "peer_id", str)
    _required(recipient, "peer_id", str)
    _required(auth, "principal_ref", str)
    scopes = _required(auth, "scopes", list)
    if not all(isinstance(scope, str) and scope for scope in scopes) or len(set(scopes)) != len(scopes):
        raise OBISRequestError("protocol.invalid_message", "authorization.scopes must be unique non-empty strings")
    _required(capability, "id", str)
    _required(capability, "version", str)
    _required(message, "payload", dict)

    issued_at = _required(message, "issued_at", (int, float))
    expires_at = _required(message, "expires_at", (int, float))
    if isinstance(issued_at, bool) or isinstance(expires_at, bool):
        raise OBISRequestError("protocol.invalid_message", "timestamps must be numeric, not boolean")
    if issued_at > now + CLOCK_SKEW_SECONDS:
        raise OBISRequestError("request.expired", "issued_at is in the future", 408)
    try:
        finite_timestamps = math.isfinite(issued_at) and math.isfinite(expires_at)
    except (OverflowError, TypeError):
        finite_timestamps = False
    if not finite_timestamps or issued_at < 0 or expires_at < 0:
        raise OBISRequestError("protocol.invalid_message", "timestamps must be finite non-negative numbers")
    if expires_at <= now or expires_at <= issued_at:
        raise OBISRequestError("request.expired", "request has expired", 408)
    if expires_at - issued_at > MAX_TTL_SECONDS:
        raise OBISRequestError("request.expired", "request TTL exceeds maximum", 408)
    if len(canonical_json(message)) > MAX_MESSAGE_BYTES:
        raise OBISRequestError("payload.too_large", "message exceeds size limit", 413)


class OBISPeer:
    """A peer with explicit credentials, capabilities, and local authorization."""

    def __init__(self, peer_id: str, credentials: list[Credential] | None = None):
        if not peer_id:
            raise ValueError("peer_id must be non-empty")
        self.peer_id = peer_id
        supplied_credentials = credentials or []
        if len({c.key_id for c in supplied_credentials}) != len(supplied_credentials):
            raise ValueError("duplicate credential key_id")
        self.credentials = {c.key_id: c for c in supplied_credentials}
        self.capabilities: dict[tuple[str, str], Capability] = {}
        self.replay_guard = ReplayGuard()
        self._lock = threading.RLock()

    def add_credential(self, credential: Credential) -> None:
        with self._lock:
            if credential.key_id in self.credentials:
                raise ValueError("duplicate credential key_id")
            self.credentials[credential.key_id] = credential

    def register_capability(
        self,
        capability_id: str,
        version: str,
        required_scopes: set[str] | frozenset[str],
        handler: Callable[[dict[str, Any]], dict[str, Any]],
        *,
        resource_binding: bool = False,
    ) -> None:
        if not capability_id or not version or not callable(handler):
            raise ValueError("capability id, version, and handler are required")
        if (
            not isinstance(required_scopes, (set, frozenset))
            or not required_scopes
            or not all(isinstance(scope, str) and scope for scope in required_scopes)
        ):
            raise ValueError("capability must declare explicit non-empty string scopes")
        key = (capability_id, version)
        with self._lock:
            if key in self.capabilities:
                raise ValueError("capability already registered")
            self.capabilities[key] = Capability(
                capability_id, version, frozenset(required_scopes), handler, resource_binding
            )

    def handle(self, message: dict[str, Any], key_id: str, signature: str) -> tuple[dict[str, Any], bytes]:
        validate_request(message)
        credential = self.credentials.get(key_id)
        if credential is None:
            raise OBISRequestError("identity.unknown_peer", "unknown credential", 401)
        if not verify_signature(message, credential.secret, signature):
            raise OBISRequestError("identity.authentication_failed", "signature verification failed", 401)

        sender = message["sender"]["peer_id"]
        recipient = message["recipient"]["peer_id"]
        if sender != credential.peer_id or recipient != self.peer_id:
            raise OBISRequestError("identity.authentication_failed", "peer identity mismatch", 401)
        if message["authorization"]["principal_ref"] != credential.principal_ref:
            raise OBISRequestError("identity.authentication_failed", "principal mismatch", 401)
        error_context = {
            "authenticated_credential": credential,
            "request_message": message,
        }
        if not self.replay_guard.accept(f"{key_id}:{message['nonce']}"):
            raise OBISRequestError("request.replay_detected", "duplicate nonce", 409, **error_context)

        cap_key = (message["capability"]["id"], message["capability"]["version"])
        capability = self.capabilities.get(cap_key)
        if capability is None:
            raise OBISRequestError("capability.unknown", "capability is not registered", 404, **error_context)

        requested_scopes = set(message["authorization"]["scopes"])
        if not capability.required_scopes.issubset(requested_scopes):
            raise OBISRequestError("authorization.denied", "required scope not requested", 403, **error_context)
        if not capability.required_scopes.issubset(credential.allowed_scopes):
            raise OBISRequestError("authorization.denied", "credential lacks required scope", 403, **error_context)
        if not requested_scopes.issubset(credential.allowed_scopes):
            raise OBISRequestError("authorization.denied", "requested scope exceeds grant", 403, **error_context)
        if capability.resource_binding:
            payload = message["payload"]
            project_id = payload.get("project_id")
            source_id = payload.get("source_id")
            if (
                not isinstance(project_id, str) or not project_id
                or not isinstance(source_id, str) or not source_id
                or (project_id, source_id) not in credential.allowed_resources
            ):
                raise OBISRequestError(
                    "authorization.denied", "project/source is outside credential resource grant",
                    403, **error_context
                )

        try:
            result = capability.handler(message["payload"])
        except Exception as exc:
            raise OBISRequestError("operation.failed", "capability execution failed", 500, **error_context) from exc
        if not isinstance(result, dict):
            raise OBISRequestError("internal.error", "capability handler must return an object", 500, **error_context)
        response = {
            "protocol": PROTOCOL,
            "version": VERSION,
            "message_type": "response",
            "message_id": secrets.token_urlsafe(18),
            "correlation_id": message["message_id"],
            "sender": {"peer_id": self.peer_id},
            "recipient": {"peer_id": sender},
            "issued_at": time.time(),
            "outcome": "succeeded",
            "result": result,
        }
        try:
            response_bytes = canonical_json(response)
        except (TypeError, ValueError, OverflowError, RecursionError) as exc:
            raise OBISRequestError(
                "operation.invalid_result", "capability returned a non-JSON result", 500, **error_context
            ) from exc
        if len(response_bytes) > MAX_MESSAGE_BYTES:
            raise OBISRequestError(
                "operation.result_too_large", "capability result exceeds response size limit", 500, **error_context
            )
        return response, credential.secret


class OBISServer:
    """Small HTTP binding for local conformance and development tests."""

    def __init__(self, peer: OBISPeer, host: str = "127.0.0.1", port: int = 0):
        if host not in ("127.0.0.1", "::1", "localhost"):
            raise ValueError("reference server is loopback-only; production transport is not implemented")
        self.peer = peer
        self.httpd = ThreadingHTTPServer((host, port), self._handler_class())
        self.thread: threading.Thread | None = None

    def _handler_class(self):
        peer = self.peer

        class Handler(BaseHTTPRequestHandler):
            server_version = "OBIS-Reference/0.1"

            def do_POST(self):
                if urlparse(self.path).path != MESSAGE_PATH:
                    self.send_error(404)
                    return
                try:
                    if self.headers.get_content_type() != "application/obis+json":
                        self.send_error(415, "unsupported content type")
                        return
                    if self.headers.get("Transfer-Encoding"):
                        self.send_error(400, "transfer encoding is not supported")
                        return
                    length = int(self.headers.get("Content-Length", "0"))
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
                    if exc.authenticated_credential is not None and exc.request_message is not None:
                        request_message = exc.request_message
                        error_response = {
                            "protocol": PROTOCOL,
                            "version": VERSION,
                            "message_type": "response",
                            "message_id": secrets.token_urlsafe(18),
                            "correlation_id": request_message["message_id"],
                            "sender": {"peer_id": peer.peer_id},
                            "recipient": {"peer_id": request_message["sender"]["peer_id"]},
                            "issued_at": time.time(),
                            "outcome": "failed",
                            "error": {"code": exc.code, "message": str(exc)},
                        }
                        body = canonical_json(error_response)
                        response_signature = hmac.new(
                            exc.authenticated_credential.secret, body, hashlib.sha256
                        ).hexdigest()
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
                # Avoid writing payloads, credentials, or peer metadata to stdout.
                return

        return Handler

    @property
    def address(self) -> str:
        host, port = self.httpd.server_address[:2]
        return f"http://{host}:{port}"

    def start(self) -> "OBISServer":
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

    def __enter__(self) -> "OBISServer":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


class OBISClient:
    """Direct client for one explicitly configured peer relationship."""

    def __init__(
        self,
        local_peer_id: str,
        remote_peer_id: str,
        key_id: str,
        principal_ref: str,
        secret: bytes,
        scopes: set[str] | frozenset[str],
        timeout: float = 3.0,
    ):
        if not local_peer_id or not remote_peer_id or not key_id or not principal_ref:
            raise ValueError("peer, key, and principal identifiers must be non-empty")
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise ValueError("reference-profile secret must be bytes of at least 32 bytes")
        if (
            not isinstance(scopes, (set, frozenset))
            or not scopes
            or not all(isinstance(scope, str) and scope for scope in scopes)
        ):
            raise ValueError("client must have explicit non-empty string scopes")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be a finite positive number")
        self.local_peer_id = local_peer_id
        self.remote_peer_id = remote_peer_id
        self.key_id = key_id
        self.principal_ref = principal_ref
        self.secret = secret
        self.scopes = frozenset(scopes)
        self.timeout = timeout

    def build_request(
        self,
        capability_id: str,
        capability_version: str,
        payload: dict[str, Any],
        scopes: set[str] | frozenset[str] | None = None,
        now: float | None = None,
    ) -> dict[str, Any]:
        requested_scopes = self.scopes if scopes is None else scopes
        if (
            not isinstance(requested_scopes, (set, frozenset))
            or not requested_scopes
            or not all(isinstance(scope, str) and scope for scope in requested_scopes)
        ):
            raise ValueError("requested scopes must be an explicit non-empty set of strings")
        if not requested_scopes.issubset(self.scopes):
            raise ValueError("requested scopes exceed the local client grant")
        issued_at = time.time() if now is None else now
        return {
            "protocol": PROTOCOL,
            "version": VERSION,
            "message_type": "request",
            "message_id": secrets.token_urlsafe(18),
            "nonce": secrets.token_urlsafe(24),
            "sender": {"peer_id": self.local_peer_id},
            "recipient": {"peer_id": self.remote_peer_id},
            "issued_at": issued_at,
            "expires_at": issued_at + MAX_TTL_SECONDS,
            "capability": {"id": capability_id, "version": capability_version},
            "authorization": {
                "principal_ref": self.principal_ref,
                "scopes": sorted(requested_scopes),
            },
            "payload": payload,
        }

    def invoke(
        self,
        endpoint: str,
        capability_id: str,
        capability_version: str,
        payload: dict[str, Any],
        scopes: set[str] | frozenset[str] | None = None,
    ) -> dict[str, Any]:
        parsed = urlparse(endpoint)
        if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "::1", "localhost"):
            raise ValueError("reference client is loopback-only; production transport is not implemented")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("endpoint must not contain user information")
        if parsed.path not in ("", "/") or parsed.params or parsed.query or parsed.fragment:
            raise ValueError("endpoint must be a bare peer base URL without path, query, or fragment")
        message = self.build_request(capability_id, capability_version, payload, scopes)
        body = canonical_json(message)
        signature = sign_message(message, self.secret)
        request = urllib.request.Request(
            endpoint.rstrip("/") + MESSAGE_PATH,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/obis+json",
                "X-OBIS-Key-Id": self.key_id,
                "X-OBIS-Signature": signature,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                response_body = response.read(MAX_MESSAGE_BYTES + 1)
                if len(response_body) > MAX_MESSAGE_BYTES:
                    raise OBISRequestError("payload.too_large", "response exceeds size limit", 502)
                response_signature = response.headers.get("X-OBIS-Signature", "")
        except urllib.error.HTTPError as exc:
            error_body = exc.read(MAX_MESSAGE_BYTES + 1)
            response_signature = exc.headers.get("X-OBIS-Signature", "")
            if error_body and response_signature:
                try:
                    if len(error_body) > MAX_MESSAGE_BYTES:
                        raise OBISRequestError("payload.too_large", "error response exceeds size limit", 502)
                    error_message = strict_json_loads(error_body.decode("utf-8"))
                    if not isinstance(error_message, dict):
                        raise OBISRequestError("protocol.invalid_message", "error response must be an object", 502)
                    if not verify_signature(error_message, self.secret, response_signature):
                        raise OBISRequestError("identity.authentication_failed", "error response signature verification failed", 502)
                    validate_response(
                        error_message, message, self.local_peer_id, self.remote_peer_id, "failed"
                    )
                    error = error_message["error"]
                    raise OBISRequestError(
                        error.get("code", "peer.request_rejected"),
                        error.get("message", f"peer returned HTTP {exc.code}"),
                        exc.code,
                    ) from exc
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as parse_exc:
                    raise OBISRequestError("protocol.invalid_message", "malformed authenticated error response", 502) from parse_exc
            raise OBISRequestError("peer.request_rejected", f"peer returned HTTP {exc.code}", exc.code) from exc
        except urllib.error.URLError as exc:
            raise OBISRequestError("peer.unavailable", "peer is unavailable", 503) from exc

        try:
            response_message = strict_json_loads(response_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
            raise OBISRequestError("protocol.invalid_message", "invalid response JSON", 502) from exc
        try:
            response_is_authentic = verify_signature(response_message, self.secret, response_signature)
        except (TypeError, ValueError, OverflowError, RecursionError) as exc:
            raise OBISRequestError("protocol.invalid_message", "response cannot be canonically encoded", 502) from exc
        if not response_is_authentic:
            raise OBISRequestError("identity.authentication_failed", "response signature verification failed", 502)
        validate_response(
            response_message, message, self.local_peer_id, self.remote_peer_id, "succeeded"
        )
        return response_message
