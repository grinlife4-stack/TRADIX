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

    def __init__(self, code: str, message: str, http_status: int = 400):
        super().__init__(message)
        self.code = code
        self.http_status = http_status


@dataclass(frozen=True)
class Credential:
    """One explicitly configured peer/principal relationship."""

    key_id: str
    peer_id: str
    principal_ref: str
    secret: bytes
    allowed_scopes: frozenset[str]

    def __post_init__(self) -> None:
        if not self.key_id or not self.peer_id or not self.principal_ref:
            raise ValueError("credential identifiers must be non-empty")
        if len(self.secret) < 32:
            raise ValueError("reference-profile secrets must be at least 32 bytes")
        if not self.allowed_scopes:
            raise ValueError("credential must have at least one explicit scope")


@dataclass(frozen=True)
class Capability:
    capability_id: str
    version: str
    required_scopes: frozenset[str]
    handler: Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class ReplayGuard:
    """Bounded in-memory replay protection for a single running peer."""

    retention_seconds: int = MAX_TTL_SECONDS + CLOCK_SKEW_SECONDS
    _seen: dict[str, float] = field(default_factory=dict)

    def accept(self, nonce: str, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        expired = [key for key, until in self._seen.items() if until <= now]
        for key in expired:
            del self._seen[key]
        if not nonce or nonce in self._seen:
            return False
        self._seen[nonce] = now + self.retention_seconds
        return True


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


def validate_request(message: dict[str, Any], now: float | None = None) -> None:
    now = time.time() if now is None else now
    if not isinstance(message, dict):
        raise OBISRequestError("protocol.invalid_message", "message must be an object")
    if message.get("protocol") != PROTOCOL or message.get("version") != VERSION:
        raise OBISRequestError("protocol.unsupported_version", "unsupported protocol/version", 426)
    if message.get("message_type") != "request":
        raise OBISRequestError("protocol.invalid_message", "message_type must be request")

    for key in ("message_id", "nonce"):
        value = _required(message, key, str)
        if not value or len(value) > 200:
            raise OBISRequestError("protocol.invalid_message", f"invalid {key}")

    sender = _required(message, "sender", dict)
    recipient = _required(message, "recipient", dict)
    auth = _required(message, "authorization", dict)
    capability = _required(message, "capability", dict)
    _required(sender, "peer_id", str)
    _required(recipient, "peer_id", str)
    _required(auth, "principal_ref", str)
    scopes = _required(auth, "scopes", list)
    if not all(isinstance(scope, str) and scope for scope in scopes):
        raise OBISRequestError("protocol.invalid_message", "authorization.scopes must be strings")
    _required(capability, "id", str)
    _required(capability, "version", str)
    _required(message, "payload", dict)

    issued_at = _required(message, "issued_at", (int, float))
    expires_at = _required(message, "expires_at", (int, float))
    if issued_at > now + CLOCK_SKEW_SECONDS:
        raise OBISRequestError("request.expired", "issued_at is in the future", 408)
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
        self.credentials = {c.key_id: c for c in (credentials or [])}
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
    ) -> None:
        if not capability_id or not version or not callable(handler):
            raise ValueError("capability id, version, and handler are required")
        key = (capability_id, version)
        with self._lock:
            if key in self.capabilities:
                raise ValueError("capability already registered")
            self.capabilities[key] = Capability(
                capability_id, version, frozenset(required_scopes), handler
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
        if not self.replay_guard.accept(f"{key_id}:{message['nonce']}"):
            raise OBISRequestError("request.replay_detected", "duplicate nonce", 409)

        cap_key = (message["capability"]["id"], message["capability"]["version"])
        capability = self.capabilities.get(cap_key)
        if capability is None:
            raise OBISRequestError("capability.unknown", "capability is not registered", 404)

        requested_scopes = set(message["authorization"]["scopes"])
        if not capability.required_scopes.issubset(requested_scopes):
            raise OBISRequestError("authorization.denied", "required scope not requested", 403)
        if not capability.required_scopes.issubset(credential.allowed_scopes):
            raise OBISRequestError("authorization.denied", "credential lacks required scope", 403)
        if not requested_scopes.issubset(credential.allowed_scopes):
            raise OBISRequestError("authorization.denied", "requested scope exceeds grant", 403)

        try:
            result = capability.handler(message["payload"])
        except Exception as exc:
            raise OBISRequestError("operation.failed", "capability execution failed", 500) from exc
        if not isinstance(result, dict):
            raise OBISRequestError("internal.error", "capability handler must return an object", 500)
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
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > MAX_MESSAGE_BYTES:
                    self.send_error(413)
                    return
                try:
                    raw = self.rfile.read(length)
                    message = json.loads(raw.decode("utf-8"))
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
                    body = canonical_json({"error": {"code": exc.code, "message": str(exc)}})
                    self.send_response(exc.http_status)
                    self.send_header("Content-Type", "application/obis+json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
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
                "scopes": sorted(self.scopes if scopes is None else scopes),
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
        if parsed.path not in ("", "/"):
            raise ValueError("endpoint must be the peer base URL")
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
            raise OBISRequestError("peer.request_rejected", f"peer returned HTTP {exc.code}", exc.code) from exc
        except urllib.error.URLError as exc:
            raise OBISRequestError("peer.unavailable", "peer is unavailable", 503) from exc

        try:
            response_message = json.loads(response_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OBISRequestError("protocol.invalid_message", "invalid response JSON", 502) from exc
        if not verify_signature(response_message, self.secret, response_signature):
            raise OBISRequestError("identity.authentication_failed", "response signature verification failed", 502)
        if response_message.get("protocol") != PROTOCOL or response_message.get("version") != VERSION:
            raise OBISRequestError("protocol.unsupported_version", "unsupported response protocol/version", 502)
        if response_message.get("message_type") != "response":
            raise OBISRequestError("protocol.invalid_message", "expected response message", 502)
        if response_message.get("correlation_id") != message["message_id"]:
            raise OBISRequestError("protocol.invalid_message", "response correlation mismatch", 502)
        if response_message.get("sender", {}).get("peer_id") != self.remote_peer_id:
            raise OBISRequestError("identity.authentication_failed", "response peer mismatch", 502)
        if response_message.get("recipient", {}).get("peer_id") != self.local_peer_id:
            raise OBISRequestError("identity.authentication_failed", "response recipient mismatch", 502)
        return response_message
