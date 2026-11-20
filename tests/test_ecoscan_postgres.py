import os

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from tools.ecoscan.oauth_refresh import TokenState
from tools.ecoscan.postgres_token_store import (
    PostgresBackendError,
    PostgresRefreshLock,
    PostgresTokenStore,
    encryption_key_from_env,
)


def test_encrypted_token_payload_round_trips_without_plaintext():
    key = AESGCM.generate_key(bit_length=256)
    store = PostgresTokenStore("postgresql://unused", key, connect=lambda _: None)
    state = TokenState(7, "access-secret-value", "refresh-secret-value", 12345.5)
    encrypted = store._encrypt(state)
    assert b"access-secret-value" not in encrypted
    assert b"refresh-secret-value" not in encrypted
    assert store._decrypt(encrypted, 7, "ACTIVE") == state


def test_encrypted_token_payload_rejects_tampering():
    key = AESGCM.generate_key(bit_length=256)
    store = PostgresTokenStore("postgresql://unused", key, connect=lambda _: None)
    encrypted = bytearray(store._encrypt(TokenState(1, "access", "refresh", 5000)))
    encrypted[-1] ^= 0x01
    with pytest.raises(PostgresBackendError, match="failed authentication"):
        store._decrypt(bytes(encrypted), 1, "ACTIVE")


def test_encryption_key_must_be_base64_32_bytes(monkeypatch):
    monkeypatch.setenv("ECOSCAN_TOKEN_ENCRYPTION_KEY", "not-base64")
    with pytest.raises(PostgresBackendError, match="base64"):
        encryption_key_from_env()
    monkeypatch.setenv("ECOSCAN_TOKEN_ENCRYPTION_KEY", "YQ==")
    with pytest.raises(PostgresBackendError, match="32 bytes"):
        encryption_key_from_env()
    monkeypatch.delenv("ECOSCAN_TOKEN_ENCRYPTION_KEY", raising=False)
    with pytest.raises(PostgresBackendError, match="not configured"):
        encryption_key_from_env()


class FakeCursor:
    def __init__(self, db):
        self.db = db
        self.rowcount = 0
        self.row = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split())
        params = params or ()
        if normalized.startswith("CREATE SCHEMA") or normalized.startswith("CREATE TABLE"):
            self.rowcount = 0
        elif "SELECT version, status, encrypted_payload" in normalized:
            self.row = self.db.get("row")
        elif normalized.startswith("INSERT INTO ecoscan.oauth_token_state"):
            if self.db.get("row") is None:
                version, status, payload = params
                self.db["row"] = (version, status, payload)
                self.rowcount = 1
            else:
                self.rowcount = 0
        elif normalized.startswith("UPDATE ecoscan.oauth_token_state"):
            new_version, status, payload, expected = params
            current = self.db.get("row")
            if current is not None and current[0] == expected:
                self.db["row"] = (new_version, status, payload)
                self.rowcount = 1
            else:
                self.rowcount = 0
        else:
            self.db.setdefault("queries", []).append((normalized, params))
            self.rowcount = 1

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, db):
        self.db = db
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return FakeCursor(self.db)

    def close(self):
        self.closed = True


def test_postgres_store_initializes_once_and_uses_versioned_cas():
    key = AESGCM.generate_key(bit_length=256)
    db = {}
    store = PostgresTokenStore("postgresql://unused", key, connect=lambda _: FakeConnection(db))
    initial = TokenState(0, "initial-access", "initial-refresh", 1000)
    assert store.initialize_state(initial) is True
    assert store.initialize_state(initial) is False
    assert store.load() == initial

    pending = TokenState(1, "initial-access", "initial-refresh", 1000, "REFRESHING")
    assert store.compare_and_swap(0, pending) is True
    assert store.load() == pending
    assert store.compare_and_swap(0, TokenState(1, "wrong", "wrong", 1)) is False


def test_postgres_store_schema_creation_is_explicit():
    key = AESGCM.generate_key(bit_length=256)
    db = {}
    store = PostgresTokenStore("postgresql://unused", key, connect=lambda _: FakeConnection(db))
    assert "row" not in db
    store.initialize_schema()
    assert "row" not in db


def test_postgres_refresh_lock_uses_session_advisory_lock_and_releases_connection():
    db = {}
    connections = []

    def connect(_):
        conn = FakeConnection(db)
        connections.append(conn)
        return conn

    lock = PostgresRefreshLock("postgresql://unused", connect=connect)
    with lock:
        assert connections[0].closed is False
        assert any("pg_advisory_lock" in q for q, _ in db["queries"])
    assert connections[0].closed is True
    assert any("pg_advisory_unlock" in q for q, _ in db["queries"])


def test_postgres_backend_rejects_transaction_pooler_for_session_lock():
    key = AESGCM.generate_key(bit_length=256)
    with pytest.raises(ValueError, match="direct PostgreSQL endpoint"):
        PostgresTokenStore("postgresql://user:pass@ep-example-pooler.us-east-2.aws.neon.tech/db", key)
    with pytest.raises(ValueError, match="direct PostgreSQL endpoint"):
        PostgresRefreshLock("postgresql://user:pass@ep-example-pooler.us-east-2.aws.neon.tech/db")


def test_bootstrap_initializes_schema_only_when_requested_and_never_overwrites(monkeypatch, capsys):
    from tools.ecoscan import bootstrap_oauth

    class FakeStore:
        def __init__(self):
            self.schema_calls = 0
            self.states = []
        def initialize_schema(self):
            self.schema_calls += 1
        def initialize_state(self, state):
            self.states.append(state)
            return len(self.states) == 1

    fake = FakeStore()
    monkeypatch.setattr(bootstrap_oauth.PostgresTokenStore, "from_env", lambda: fake)
    monkeypatch.setenv("RAILWAY_OAUTH_INITIAL_ACCESS_TOKEN", "initial-access-secret")
    monkeypatch.setenv("RAILWAY_OAUTH_INITIAL_REFRESH_TOKEN", "initial-refresh-secret")
    monkeypatch.setenv("RAILWAY_OAUTH_ACCESS_EXPIRES_IN", "3600")

    assert bootstrap_oauth.main(["--create-schema"]) == 0
    assert fake.schema_calls == 1
    assert fake.states[0].version == 0
    assert fake.states[0].status == "ACTIVE"
    assert fake.states[0].access_token == "initial-access-secret"
    assert "initial-access-secret" not in capsys.readouterr().out

    assert bootstrap_oauth.main([]) == 3
    assert fake.schema_calls == 1
    assert len(fake.states) == 2


def test_postgres_backend_requires_explicit_postgresql_uri():
    key = AESGCM.generate_key(bit_length=256)
    with pytest.raises(ValueError, match="explicit host"):
        PostgresTokenStore("host=somewhere dbname=neondb", key)
