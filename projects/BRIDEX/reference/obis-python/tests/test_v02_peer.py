import hashlib
import json
import time
from pathlib import Path

import pytest

from obis_bridge.operations import OperationLedger
from obis_bridge.peer import Credential, OBISPeer, OBISRequestError, ReplayGuard, sign_message
from obis_bridge.v02 import OBISPeerV02, OBISV02Client, OBISV02Server, operation_request_hash


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


def test_v02_loopback_http_client_executes_once_and_recovers_status(tmp_path):
    from obis_bridge.v02 import OBISV02Client, OBISV02Server

    calls = []
    credential = Credential(
        key_id="caller-key", peer_id="peer:caller", principal_ref="principal:caller",
        secret=SECRET, allowed_scopes=frozenset({"records:write"}),
    )
    base = OBISPeer("peer:owner", [credential], replay_guard=ReplayGuard())
    peer = OBISPeerV02(base, OperationLedger(tmp_path / "http-operations.sqlite3"))
    peer.register_capability(
        "records.write", "1.0", {"records:write"},
        lambda payload: calls.append(payload) or {"written": True},
        recovery_class="IDEMPOTENT",
    )
    client = OBISV02Client(
        "peer:caller", "peer:owner", "caller-key", "principal:caller",
        SECRET, {"records:write"},
    )
    with OBISV02Server(peer) as server:
        first = client.invoke(
            server.address, "records.write", "1.0", {"record_id": "http-1"},
            operation_id="http-op-1", idempotency_key="http-idem-1",
        )
        duplicate = client.invoke(
            server.address, "records.write", "1.0", {"record_id": "http-1"},
            operation_id="http-op-1", idempotency_key="http-idem-1",
        )
        status = client.status(server.address, "records.write", "1.0", "http-op-1")
    assert first["operation"]["state"] == "SUCCEEDED"
    assert duplicate["operation"]["result"] == {"written": True}
    assert status["operation"]["state"] == "SUCCEEDED"
    assert len(calls) == 1


def test_v02_resource_bound_status_cannot_read_another_allowed_resource(tmp_path):
    from obis_bridge.peer import OBISRequestError

    credential = Credential(
        key_id="caller-key", peer_id="peer:caller", principal_ref="principal:caller",
        secret=SECRET, allowed_scopes=frozenset({"records:write"}),
        allowed_resources=frozenset({("project-a", "source-a"), ("project-b", "source-b")}),
    )
    base = OBISPeer("peer:owner", [credential], replay_guard=ReplayGuard())
    ledger = OperationLedger(tmp_path / "resource-bound.sqlite3")
    peer = OBISPeerV02(base, ledger)
    peer.register_capability(
        "records.write", "1.0", {"records:write"},
        lambda payload: {"resource": payload["project_id"] + "/" + payload["source_id"]},
        recovery_class="IDEMPOTENT", resource_binding=True,
    )
    request = make_request()
    request["payload"] = {"project_id": "project-a", "source_id": "source-a"}
    request["operation"]["request_hash"] = operation_request_hash(request)
    response, _ = signed(peer, request)
    assert response["operation"]["state"] == "SUCCEEDED"

    status = {
        "protocol": "obis", "version": "0.2", "message_type": "operation_status_request",
        "message_id": "status-resource-1", "nonce": "status-resource-nonce",
        "attempt_id": "status-resource-attempt",
        "sender": {"peer_id": "peer:caller"}, "recipient": {"peer_id": "peer:owner"},
        "issued_at": time.time(), "expires_at": time.time() + 30,
        "capability": {"id": "records.write", "version": "1.0"},
        "authorization": {"principal_ref": "principal:caller", "scopes": ["records:write"]},
        "operation_id": "op-1",
        "resource": {"project_id": "project-b", "source_id": "source-b"},
    }
    with pytest.raises(OBISRequestError, match="operation not found"):
        signed(peer, status)



def test_operation_request_hash_uses_shared_contract_vectors():
    vector_path = (
        Path(__file__).resolve().parents[2]
        / "obis-contract"
        / "testdata"
        / "operation-request-hash-vectors.json"
    )
    fixture = json.loads(vector_path.read_text(encoding="utf-8"))
    assert fixture["schema_version"] == "0.2"
    assert fixture["vectors"]
    for vector in fixture["vectors"]:
        assert operation_request_hash(vector["message"]) == vector["sha256"], vector["name"]



def test_v02_authenticated_authorization_error_is_signed_and_correlated(tmp_path):
    credential = Credential(
        key_id="caller-key", peer_id="peer:caller", principal_ref="principal:caller",
        secret=SECRET, allowed_scopes=frozenset({"records:write"}),
        allowed_resources=frozenset({("project-a", "source-a")}),
    )
    base = OBISPeer("peer:owner", [credential], replay_guard=ReplayGuard())
    peer = OBISPeerV02(base, OperationLedger(tmp_path / "signed-errors.sqlite3"))
    calls = []
    peer.register_capability(
        "records.write", "1.0", {"records:write"},
        lambda payload: calls.append(payload) or {"accepted": True},
        recovery_class="IDEMPOTENT", resource_binding=True,
    )
    client = OBISV02Client(
        "peer:caller", "peer:owner", "caller-key", "principal:caller",
        SECRET, {"records:write"},
    )
    with OBISV02Server(peer) as server:
        with pytest.raises(OBISRequestError) as raised:
            client.invoke(
                server.address, "records.write", "1.0",
                {"project_id": "project-b", "source_id": "source-b"},
                operation_id="signed-error-op", idempotency_key="signed-error-idem",
            )
    assert raised.value.code == "authorization.denied"
    assert raised.value.http_status == 403
    assert calls == []



def test_v02_rejects_ambiguous_slash_resource_identity(tmp_path):
    calls = []
    credential = Credential(
        key_id="caller-key",
        peer_id="peer:caller",
        principal_ref="principal:caller",
        secret=SECRET,
        allowed_scopes=frozenset({"inventory.read"}),
        allowed_resources=frozenset({("project-a/source-a", "source-b")}),
    )
    base = OBISPeer("peer:owner", [credential], replay_guard=ReplayGuard())
    peer = OBISPeerV02(base, OperationLedger(tmp_path / "resource-identity.sqlite3"))
    peer.register_capability(
        "ecoscan.inventory.read", "1.0", {"inventory.read"},
        lambda payload: calls.append(payload) or {"ok": True},
        recovery_class="IDEMPOTENT", resource_binding=True,
    )
    message = make_request(payload={
        "project_id": "project-a/source-a",
        "source_id": "source-b",
    })
    message["capability"] = {"id": "ecoscan.inventory.read", "version": "1.0"}
    message["authorization"] = {
        "principal_ref": "principal:caller",
        "scopes": ["inventory.read"],
    }
    message["operation"]["request_hash"] = operation_request_hash(message)
    with pytest.raises(OBISRequestError) as raised:
        peer.handle(message, "caller-key", sign_message(message, SECRET))
    assert raised.value.code == "authorization.denied"
    assert calls == []
