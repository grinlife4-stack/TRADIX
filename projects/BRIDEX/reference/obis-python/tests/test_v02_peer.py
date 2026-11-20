import hashlib
import time

import pytest

from obis_bridge.operations import OperationLedger
from obis_bridge.peer import Credential, OBISPeer, ReplayGuard, sign_message
from obis_bridge.v02 import OBISPeerV02, operation_request_hash


SECRET = b"0123456789abcdef0123456789abcdef"


def make_peer(tmp_path, handler):
    credential = Credential(
        key_id="caller-key", peer_id="peer:caller", principal_ref="principal:caller",
        secret=SECRET, allowed_scopes=frozenset({"records:write", "records:read"}),
    )
    base = OBISPeer("peer:owner", [credential], replay_guard=ReplayGuard())
    ledger = OperationLedger(tmp_path / "operations.sqlite3")
    peer = OBISPeerV02(base, ledger)
    peer.register_capability(
        "records.write", "1.0", {"records:write"}, handler,
        recovery_class="NON_RECOVERABLE",
    )
    return peer, ledger


def make_request(now=None, *, operation_id="op-1", nonce="nonce-1", payload=None):
    now = time.time() if now is None else now
    message = {
        "protocol": "obis", "version": "0.2", "message_type": "request",
        "message_id": "message-" + nonce, "nonce": nonce, "attempt_id": "attempt-" + nonce,
        "sender": {"peer_id": "peer:caller"}, "recipient": {"peer_id": "peer:owner"},
        "issued_at": now, "expires_at": now + 30,
        "capability": {"id": "records.write", "version": "1.0"},
        "authorization": {"principal_ref": "principal:caller", "scopes": ["records:write"]},
        "operation": {
            "operation_id": operation_id, "idempotency_key": "idem-1",
            "request_hash": "", "expires_at": now + 300,
        },
        "payload": payload or {"record_id": "record-1"},
    }
    message["operation"]["request_hash"] = operation_request_hash(message)
    return message


def signed(peer, message):
    return peer.handle(message, "caller-key", sign_message(message, SECRET))


def test_v02_executes_once_and_duplicate_recovers_committed_result(tmp_path):
    calls = []
    peer, _ = make_peer(tmp_path, lambda payload: calls.append(payload) or {"written": True})
    first = make_request()
    response, _ = signed(peer, first)
    second = make_request(operation_id="op-1", nonce="nonce-2")
    second["operation"]["idempotency_key"] = "idem-1"
    second["operation"]["request_hash"] = operation_request_hash(second)
    recovered, _ = signed(peer, second)
    assert response["operation"]["state"] == "SUCCEEDED"
    assert recovered["operation"]["result"] == {"written": True}
    assert len(calls) == 1


def test_v02_handler_exception_becomes_unknown_not_failed(tmp_path):
    def uncertain(_):
        raise RuntimeError("provider response lost after possible side effect")
    peer, _ = make_peer(tmp_path, uncertain)
    response, _ = signed(peer, make_request())
    assert response["operation"]["state"] == "UNKNOWN"
    assert response["operation"]["failure_code"] == "operation.outcome_unknown"


def test_v02_hash_mismatch_is_rejected_before_handler(tmp_path):
    calls = []
    peer, _ = make_peer(tmp_path, lambda payload: calls.append(payload) or {"ok": True})
    request = make_request()
    request["payload"]["record_id"] = "tampered"
    with pytest.raises(Exception, match="request hash verification failed"):
        signed(peer, request)
    assert calls == []


def test_v02_status_lookup_requires_authenticated_scope(tmp_path):
    peer, _ = make_peer(tmp_path, lambda payload: {"ok": True})
    request = make_request()
    signed(peer, request)
    status = {
        "protocol": "obis", "version": "0.2", "message_type": "operation_status_request",
        "message_id": "status-1", "nonce": "status-nonce", "attempt_id": "status-attempt",
        "sender": {"peer_id": "peer:caller"}, "recipient": {"peer_id": "peer:owner"},
        "issued_at": time.time(), "expires_at": time.time() + 30,
        "capability": {"id": "records.write", "version": "1.0"},
        "authorization": {"principal_ref": "principal:caller", "scopes": ["records:write"]},
        "operation_id": "op-1",
    }
    response, _ = signed(peer, status)
    assert response["operation"]["state"] == "SUCCEEDED"
