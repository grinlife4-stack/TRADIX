"""One-time, fail-closed seed of the initial Railway OAuth token pair.

Required environment:
  ECOSCAN_DATABASE_URL
  ECOSCAN_TOKEN_ENCRYPTION_KEY (base64-encoded 32-byte AES-256 key)
  RAILWAY_OAUTH_INITIAL_ACCESS_TOKEN
  RAILWAY_OAUTH_INITIAL_REFRESH_TOKEN
Optional:
  RAILWAY_OAUTH_ACCESS_EXPIRES_IN (seconds; defaults to Railway's 3600)

Run with --create-schema only when an approved schema migration is intended.
Existing token state is never overwritten.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

from .oauth_refresh import TokenState
from .postgres_token_store import PostgresBackendError, PostgresTokenStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Initialize ECOSCAN Railway OAuth state once")
    parser.add_argument(
        "--create-schema",
        action="store_true",
        help="Explicitly create the ECOSCAN schema and token-state table",
    )
    args = parser.parse_args(argv)

    access = os.environ.get("RAILWAY_OAUTH_INITIAL_ACCESS_TOKEN", "")
    refresh = os.environ.get("RAILWAY_OAUTH_INITIAL_REFRESH_TOKEN", "")
    try:
        expires_in = int(os.environ.get("RAILWAY_OAUTH_ACCESS_EXPIRES_IN", "3600"))
    except ValueError:
        print("Bootstrap failed: invalid access-token lifetime", file=sys.stderr)
        return 2
    if not access or not refresh or expires_in <= 0:
        print("Bootstrap failed: initial OAuth token pair is incomplete", file=sys.stderr)
        return 2

    try:
        store = PostgresTokenStore.from_env()
        if args.create_schema:
            store.initialize_schema()
        state = TokenState(
            version=0,
            access_token=access,
            refresh_token=refresh,
            expires_at=time.time() + expires_in,
            status="ACTIVE",
        )
        if store.initialize_state(state):
            print("ECOSCAN OAuth state initialized; token values were not displayed.")
            return 0
        print("ECOSCAN OAuth state already exists; no values were changed.", file=sys.stderr)
        return 3
    except (PostgresBackendError, ValueError):
        print("Bootstrap failed: PostgreSQL configuration or persistence error", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
