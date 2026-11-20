"""Safe Railway OAuth refresh orchestration.

This module deliberately contains no concrete persistence or locking backend.
Production use requires a durable TokenStore with atomic compare-and-swap and a
cross-process RefreshLock. In-memory or per-process locks are not production
implementations.
"""
from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import ContextManager, Protocol


TOKEN_ENDPOINT = "https://backboard.railway.com/oauth/token"


class RefreshError(RuntimeError):
    """Sanitized refresh failure; never includes credentials or response bodies."""


@dataclass(frozen=True)
class TokenState:
    version: int
    access_token: str
    refresh_token: str
    expires_at: float


class TokenStore(Protocol):
    """Durable store contract; CAS must atomically replace the whole token state."""

    def load(self) -> TokenState | None: ...

    def compare_and_swap(self, expected_version: int, replacement: TokenState) -> bool: ...


class RefreshLock(Protocol):
    """Must serialize refreshes across every runner sharing the TokenStore."""

    def __enter__(self) -> object: ...
    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool | None: ...


def _request_rotated_tokens(
    client_id: str,
    client_secret: str,
    refresh_token: str,
    *,
    timeout: float = 15.0,
    opener=urllib.request.urlopen,
) -> tuple[str, str, int]:
    if not client_id or not client_secret or not refresh_token:
        raise RefreshError("OAuth client credentials and refresh token are required")

    basic = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    body = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }).encode("ascii")
    request = urllib.request.Request(
        TOKEN_ENDPOINT,
        data=body,
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": "ECOSCAN",
        },
        method="POST",
    )
    try:
        with opener(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Do not expose response bodies: OAuth servers may echo sensitive input.
        raise RefreshError(f"Railway OAuth token endpoint returned HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise RefreshError("Railway OAuth token endpoint is unavailable") from None
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise RefreshError("Railway OAuth token endpoint returned invalid JSON") from None

    if not isinstance(payload, dict):
        raise RefreshError("Railway OAuth token response has an invalid shape")
    access = payload.get("access_token")
    rotated = payload.get("refresh_token")
    expires_in = payload.get("expires_in")
    if not isinstance(access, str) or not access:
        raise RefreshError("Railway OAuth response omitted access_token")
    if not isinstance(rotated, str) or not rotated:
        raise RefreshError("Railway OAuth response omitted refresh_token; refusing unsafe continuation")
    if isinstance(expires_in, bool) or not isinstance(expires_in, (int, float)) or expires_in <= 0:
        raise RefreshError("Railway OAuth response has invalid expires_in")
    return access, rotated, int(expires_in)


def get_valid_access_token(
    store: TokenStore,
    lock: RefreshLock,
    client_id: str,
    client_secret: str,
    *,
    now: float | None = None,
    refresh_skew_seconds: int = 120,
    timeout: float = 15.0,
    opener=urllib.request.urlopen,
) -> str:
    """Return a valid access token, persisting rotation before releasing the lock.

    The lock must be distributed/shared by all scheduled and manual runners.
    The store must durably commit CAS before returning True. Any uncertainty
    fails closed; callers must not proceed to Railway GraphQL without a token.
    """
    if refresh_skew_seconds < 0:
        raise ValueError("refresh_skew_seconds must not be negative")
    with lock:
        current = store.load()
        if current is None:
            raise RefreshError("No persisted Railway OAuth token state is configured")

        current_time = time.time() if now is None else now
        if current.access_token and current.expires_at > current_time + refresh_skew_seconds:
            return current.access_token

        access, refresh, expires_in = _request_rotated_tokens(
            client_id,
            client_secret,
            current.refresh_token,
            timeout=timeout,
            opener=opener,
        )
        replacement = TokenState(
            version=current.version + 1,
            access_token=access,
            refresh_token=refresh,
            expires_at=current_time + expires_in,
        )
        if not store.compare_and_swap(current.version, replacement):
            # Never return the access token if durable rotation was not committed.
            raise RefreshError("Token state changed concurrently or durable commit failed")
        return access
