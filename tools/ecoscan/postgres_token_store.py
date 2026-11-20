"""PostgreSQL-backed, encrypted Railway OAuth token state and distributed lock.

No schema is created implicitly. Call initialize_schema() only during an
approved deployment/migration. Token values are encrypted in the application
before they reach PostgreSQL; the encryption key must be stored separately.
"""
from __future__ import annotations

import base64
import json
import os
from urllib.parse import urlsplit
from contextlib import AbstractContextManager
from typing import Callable

from .oauth_refresh import RefreshError, TokenState

_SCHEMA = "ecoscan"
_TABLE = "oauth_token_state"
_AAD = b"TRADIX/ECOSCAN/railway-oauth/v1"
_LOCK_ID = 0x45434F5343414E  # stable signed-64-bit advisory lock key


class PostgresBackendError(RuntimeError):
    """Sanitized persistence or locking error."""


def _require_direct_connection(dsn: str) -> None:
    try:
        parsed = urlsplit(dsn)
        hostname = parsed.hostname or ""
    except ValueError:
        raise ValueError("invalid PostgreSQL DSN") from None
    if parsed.scheme not in {"postgres", "postgresql"} or not hostname:
        raise ValueError("ECOSCAN requires a PostgreSQL URI with an explicit host")
    if "-pooler" in hostname.lower():
        raise ValueError(
            "ECOSCAN requires a direct PostgreSQL endpoint for session advisory locks"
        )


def _load_aesgcm():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:
        raise PostgresBackendError(
            "cryptography is required for encrypted PostgreSQL token storage"
        ) from exc
    return AESGCM


def _connect(dsn: str):
    try:
        import psycopg
    except ImportError as exc:
        raise PostgresBackendError("psycopg is required for PostgreSQL token storage") from exc
    try:
        return psycopg.connect(dsn, connect_timeout=10, sslmode="require")
    except Exception:
        raise PostgresBackendError("PostgreSQL connection failed") from None


def encryption_key_from_env(name: str = "ECOSCAN_TOKEN_ENCRYPTION_KEY") -> bytes:
    value = os.environ.get(name, "")
    if not value:
        raise PostgresBackendError("Token encryption key is not configured")
    try:
        key = base64.b64decode(value, validate=True)
    except (ValueError, TypeError):
        raise PostgresBackendError("Token encryption key must be base64-encoded") from None
    if len(key) != 32:
        raise PostgresBackendError("Token encryption key must decode to exactly 32 bytes")
    return key


class PostgresTokenStore:
    """CAS token store. Construction is read/write inert; schema setup is explicit."""

    def __init__(
        self,
        dsn: str,
        encryption_key: bytes,
        *,
        connect: Callable | None = None,
    ):
        if not dsn:
            raise ValueError("dsn is required")
        _require_direct_connection(dsn)
        if len(encryption_key) != 32:
            raise ValueError("AES-256-GCM key must be exactly 32 bytes")
        self._dsn = dsn
        self._key = bytes(encryption_key)
        self._connect = connect or _connect

    @classmethod
    def from_env(cls, *, connect: Callable | None = None) -> "PostgresTokenStore":
        dsn = os.environ.get("ECOSCAN_DATABASE_URL", "")
        if not dsn:
            raise PostgresBackendError("ECOSCAN_DATABASE_URL is not configured")
        return cls(dsn, encryption_key_from_env(), connect=connect)

    def _encrypt(self, state: TokenState) -> bytes:
        AESGCM = _load_aesgcm()
        nonce = os.urandom(12)
        payload = json.dumps({
            "access_token": state.access_token,
            "refresh_token": state.refresh_token,
            "expires_at": state.expires_at,
        }, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return nonce + AESGCM(self._key).encrypt(nonce, payload, _AAD)

    def _decrypt(self, blob: bytes, version: int, status: str) -> TokenState:
        AESGCM = _load_aesgcm()
        if not isinstance(blob, (bytes, bytearray)) or len(blob) < 29:
            raise PostgresBackendError("Persisted token payload is invalid")
        try:
            payload = json.loads(AESGCM(self._key).decrypt(
                bytes(blob[:12]), bytes(blob[12:]), _AAD
            ).decode("utf-8"))
            access = payload["access_token"]
            refresh = payload["refresh_token"]
            expires = payload["expires_at"]
            if (not isinstance(access, str) or not access
                    or not isinstance(refresh, str) or not refresh
                    or isinstance(expires, bool) or not isinstance(expires, (int, float))
                    or status not in {"ACTIVE", "REFRESHING"}):
                raise ValueError("invalid state")
            return TokenState(int(version), access, refresh, float(expires), status)
        except Exception:
            raise PostgresBackendError(
                "Persisted token payload failed authentication or validation"
            ) from None

    def initialize_schema(self) -> None:
        """Explicit one-time migration; never called automatically."""
        try:
            with self._connect(self._dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute("CREATE SCHEMA IF NOT EXISTS ecoscan")
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS ecoscan.oauth_token_state (
                            singleton SMALLINT PRIMARY KEY CHECK (singleton = 1),
                            version BIGINT NOT NULL CHECK (version >= 0),
                            status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'REFRESHING')),
                            encrypted_payload BYTEA NOT NULL,
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                        )
                    """)
        except PostgresBackendError:
            raise
        except Exception:
            raise PostgresBackendError("Could not initialize ECOSCAN token schema") from None

    def initialize_state(self, state: TokenState) -> bool:
        """Insert the initial state once. Never overwrites an existing token."""
        if state.version != 0 or state.status != "ACTIVE":
            raise ValueError("initial token state must be ACTIVE at version 0")
        encrypted = self._encrypt(state)
        try:
            with self._connect(self._dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO ecoscan.oauth_token_state
                            (singleton, version, status, encrypted_payload)
                        VALUES (1, %s, %s, %s)
                        ON CONFLICT (singleton) DO NOTHING
                    """, (state.version, state.status, encrypted))
                    return cur.rowcount == 1
        except Exception:
            raise PostgresBackendError("Could not initialize ECOSCAN token state") from None

    def load(self) -> TokenState | None:
        try:
            with self._connect(self._dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT version, status, encrypted_payload
                        FROM ecoscan.oauth_token_state
                        WHERE singleton = 1
                    """)
                    row = cur.fetchone()
        except Exception:
            raise PostgresBackendError("Could not load ECOSCAN token state") from None
        if row is None:
            return None
        return self._decrypt(row[2], row[0], row[1])

    def compare_and_swap(self, expected_version: int, replacement: TokenState) -> bool:
        if replacement.version != expected_version + 1:
            raise ValueError("replacement version must increment exactly once")
        if replacement.status not in {"ACTIVE", "REFRESHING"}:
            raise ValueError("invalid token state status")
        encrypted = self._encrypt(replacement)
        try:
            with self._connect(self._dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE ecoscan.oauth_token_state
                        SET version = %s, status = %s, encrypted_payload = %s,
                            updated_at = now()
                        WHERE singleton = 1 AND version = %s
                    """, (
                        replacement.version, replacement.status, encrypted,
                        expected_version,
                    ))
                    return cur.rowcount == 1
        except Exception:
            raise PostgresBackendError("Could not commit ECOSCAN token state") from None


class PostgresRefreshLock(AbstractContextManager):
    """Session-scoped PostgreSQL advisory lock shared by all runners."""

    def __init__(self, dsn: str, *, connect: Callable | None = None):
        if not dsn:
            raise ValueError("dsn is required")
        _require_direct_connection(dsn)
        self._dsn = dsn
        self._connect = connect or _connect
        self._conn = None

    @classmethod
    def from_env(cls, *, connect: Callable | None = None) -> "PostgresRefreshLock":
        dsn = os.environ.get("ECOSCAN_DATABASE_URL", "")
        if not dsn:
            raise PostgresBackendError("ECOSCAN_DATABASE_URL is not configured")
        return cls(dsn, connect=connect)

    def __enter__(self):
        if self._conn is not None:
            raise PostgresBackendError("Refresh lock instance cannot be re-entered")
        try:
            self._conn = self._connect(self._dsn)
            with self._conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_lock(%s)", (_LOCK_ID,))
            return self
        except Exception:
            if self._conn is not None:
                self._conn.close()
                self._conn = None
            raise PostgresBackendError("Could not acquire distributed refresh lock") from None

    def __exit__(self, exc_type, exc, traceback):
        conn, self._conn = self._conn, None
        if conn is None:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_unlock(%s)", (_LOCK_ID,))
        except Exception:
            # Closing the session releases the PostgreSQL advisory lock.
            pass
        finally:
            conn.close()
        return False
