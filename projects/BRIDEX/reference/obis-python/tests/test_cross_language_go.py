import json
import os
import subprocess
import urllib.error
import urllib.request

import pytest

from obis_bridge import OBISClient, OBISPeer, OBISServer, Credential, OBISRequestError
from obis_bridge.peer import canonical_json, sign_message, validate_response, verify_signature


GO_PEER_BINARY = os.environ.get("OBIS_GO_PEER_BINARY")
SECRET = b"0123456789abcdef0123456789abcdef"


pytestmark = pytest.mark.skipif(
    not GO_PEER_BINARY or not os.path.isfile(GO_PEER_BINARY),
    reason="independent Go peer binary is built by the repository CI workflow",
)


def _start_go_server(replay_dir=None):
    command = [
        GO_PEER_BINARY,
        "--peer-id", "peer:go",
        "--listen", "127.0.0.1:0",
        "--key-id", "python-dev-key",
        "--remote-peer", "peer:python",
        "--principal", "principal:python",
        "--secret-hex", SECRET.hex(),
        "--scopes", "records:read",
    ]
    if replay_dir is not None:
        command.extend(["--replay-dir", str(replay_dir)])
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    address = process.stdout.readline().strip()
    if not address:
        stderr = process.stderr.read() if process.stderr else ""
        process.kill()
        raise AssertionError(f"Go peer did not publish its loopback address: {stderr}")
    return process, f"http://{address}"


def test_python_reference_client_invokes_independent_go_peer():
    process, endpoint = _start_go_server()
    try:
        client = OBISClient(
            local_peer_id="peer:python",
            remote_peer_id="peer:go",
            key_id="python-dev-key",
            principal_ref="principal:python",
            secret=SECRET,
            scopes={"records:read"},
        )
        response = client.invoke(
            endpoint,
            "records.read",
            "1.0",
            {"record_id": "python-to-go"},
        )
        assert response["outcome"] == "succeeded"
        assert response["result"] == {
            "record_id": "python-to-go",
            "served_by": "go-peer",
        }
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_independent_go_client_invokes_python_reference_peer():
    credential = Credential(
        key_id="go-dev-key",
        peer_id="peer:go",
        principal_ref="principal:go",
        secret=SECRET,
        allowed_scopes=frozenset({"records:read"}),
    )
    peer = OBISPeer("peer:python", [credential])
    peer.register_capability(
        "records.read",
        "1.0",
        {"records:read"},
        lambda payload: {
            "record_id": payload["record_id"],
            "served_by": "python-peer",
        },
    )
    with OBISServer(peer) as server:
        result = subprocess.run(
            [
                GO_PEER_BINARY,
                "invoke",
                "--local-peer", "peer:go",
                "--endpoint", server.address,
                "--remote-peer", "peer:python",
                "--key-id", "go-dev-key",
                "--principal", "principal:go",
                "--secret-hex", SECRET.hex(),
                "--scopes", "records:read",
                "--capability", "records.read",
                "--capability-version", "1.0",
                "--payload", json.dumps({"record_id": "go-to-python"}),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    response = json.loads(result.stdout)
    assert response["outcome"] == "succeeded"
    assert response["result"] == {
        "record_id": "go-to-python",
        "served_by": "python-peer",
    }


def test_go_peer_returns_signed_correlated_error_to_python_client():
    process, endpoint = _start_go_server()
    try:
        client = OBISClient(
            local_peer_id="peer:python", remote_peer_id="peer:go",
            key_id="python-dev-key", principal_ref="principal:python",
            secret=SECRET, scopes={"records:read"},
        )
        with pytest.raises(OBISRequestError) as exc:
            client.invoke(endpoint, "missing.capability", "1.0", {"record_id": "x"})
        assert exc.value.code == "capability.unknown"
        assert exc.value.http_status == 404
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_go_client_validates_signed_error_from_python_peer():
    credential = Credential(
        key_id="go-dev-key", peer_id="peer:go", principal_ref="principal:go",
        secret=SECRET, allowed_scopes=frozenset({"records:read"}),
    )
    peer = OBISPeer("peer:python", [credential])
    peer.register_capability(
        "records.read", "1.0", {"records:read"},
        lambda payload: {"record_id": payload["record_id"]},
    )
    with OBISServer(peer) as server:
        result = subprocess.run(
            [
                GO_PEER_BINARY, "invoke",
                "--local-peer", "peer:go", "--endpoint", server.address,
                "--remote-peer", "peer:python", "--key-id", "go-dev-key",
                "--principal", "principal:go", "--secret-hex", SECRET.hex(),
                "--scopes", "records:write", "--capability", "records.read",
                "--capability-version", "1.0", "--payload", json.dumps({"record_id": "denied"}),
            ],
            capture_output=True, text=True, timeout=10,
        )
    assert result.returncode != 0
    assert "authorization.denied" in result.stderr


def test_python_client_validates_authenticated_error_from_go_peer():
    process, endpoint = _start_go_server()
    try:
        client = OBISClient(
            local_peer_id="peer:python",
            remote_peer_id="peer:go",
            key_id="python-dev-key",
            principal_ref="principal:python",
            secret=SECRET,
            scopes={"records:read"},
        )
        with pytest.raises(OBISRequestError) as raised:
            client.invoke(endpoint, "missing.capability", "1.0", {"record_id": "unknown"})
        assert raised.value.code == "capability.unknown"
        assert raised.value.http_status == 404
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_go_client_validates_authenticated_error_from_python_peer():
    calls = []
    credential = Credential(
        key_id="go-dev-key",
        peer_id="peer:go",
        principal_ref="principal:go",
        secret=SECRET,
        allowed_scopes=frozenset({"records:read"}),
    )
    peer = OBISPeer("peer:python", [credential])
    peer.register_capability(
        "records.read", "1.0", {"records:read"},
        lambda payload: calls.append(payload) or {"record_id": payload["record_id"]},
    )
    with OBISServer(peer) as server:
        result = subprocess.run(
            [
                GO_PEER_BINARY,
                "invoke",
                "--local-peer", "peer:go",
                "--endpoint", server.address,
                "--remote-peer", "peer:python",
                "--key-id", "go-dev-key",
                "--principal", "principal:go",
                "--secret-hex", SECRET.hex(),
                "--scopes", "records:read",
                "--capability", "missing.capability",
                "--capability-version", "1.0",
                "--payload", json.dumps({"record_id": "missing"}),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    assert result.returncode != 0
    assert "capability.unknown" in result.stderr
    assert calls == []


def test_python_client_receives_signed_scope_denial_from_go_peer():
    process, endpoint = _start_go_server()
    try:
        client = OBISClient(
            local_peer_id="peer:python",
            remote_peer_id="peer:go",
            key_id="python-dev-key",
            principal_ref="principal:python",
            secret=SECRET,
            scopes={"records:write"},
        )
        with pytest.raises(OBISRequestError) as raised:
            client.invoke(endpoint, "records.read", "1.0", {"record_id": "denied"})
        assert raised.value.code == "authorization.denied"
        assert raised.value.http_status == 403
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_go_client_receives_signed_scope_denial_from_python_peer():
    calls = []
    credential = Credential(
        key_id="go-dev-key",
        peer_id="peer:go",
        principal_ref="principal:go",
        secret=SECRET,
        allowed_scopes=frozenset({"records:read"}),
    )
    peer = OBISPeer("peer:python", [credential])
    peer.register_capability(
        "records.read", "1.0", {"records:read"},
        lambda payload: calls.append(payload) or {"record_id": payload["record_id"]},
    )
    with OBISServer(peer) as server:
        result = subprocess.run(
            [
                GO_PEER_BINARY,
                "invoke",
                "--local-peer", "peer:go",
                "--endpoint", server.address,
                "--remote-peer", "peer:python",
                "--key-id", "go-dev-key",
                "--principal", "principal:go",
                "--secret-hex", SECRET.hex(),
                "--scopes", "records:write",
                "--capability", "records.read",
                "--capability-version", "1.0",
                "--payload", json.dumps({"record_id": "denied"}),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    assert result.returncode != 0
    assert "authorization.denied" in result.stderr
    assert calls == []



def _post_raw_with_headers(endpoint, message, signature):
    request = urllib.request.Request(
        endpoint.rstrip("/") + "/obis/v0.1/messages",
        data=canonical_json(message),
        method="POST",
        headers={
            "Content-Type": "application/obis+json",
            "X-OBIS-Key-Id": "python-dev-key",
            "X-OBIS-Signature": signature,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            return response.status, response.read(), response.headers.get("X-OBIS-Signature", "")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), exc.headers.get("X-OBIS-Signature", "")


def _post_raw(endpoint, message, signature):
    status, body, _ = _post_raw_with_headers(endpoint, message, signature)
    return status, body


def _assert_signed_error_response(request, status, body, response_signature, expected_status, expected_code):
    assert status == expected_status
    response = json.loads(body.decode("utf-8"))
    assert verify_signature(response, SECRET, response_signature)
    validate_response(response, request, "peer:python", "peer:go", "failed")
    assert response["error"]["code"] == expected_code



def _post_raw_bytes(endpoint, body, signature=""):
    request = urllib.request.Request(
        endpoint.rstrip("/") + "/obis/v0.1/messages",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/obis+json",
            "X-OBIS-Key-Id": "python-dev-key",
            "X-OBIS-Signature": signature,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()

def test_python_raw_malformed_and_unauthenticated_requests_are_rejected_by_go_peer():
    process, endpoint = _start_go_server()
    try:
        client = OBISClient(
            local_peer_id="peer:python", remote_peer_id="peer:go",
            key_id="python-dev-key", principal_ref="principal:python",
            secret=SECRET, scopes={"records:read"},
        )
        malformed = client.build_request("records.read", "1.0", {"record_id": "bad-version"})
        malformed["version"] = "0.2"
        status, _ = _post_raw(endpoint, malformed, sign_message(malformed, SECRET))
        assert status == 426

        unauthenticated = client.build_request("records.read", "1.0", {"record_id": "bad-signature"})
        status, _ = _post_raw(endpoint, unauthenticated, "00" * 32)
        assert status == 401
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_go_format_malformed_and_unauthenticated_requests_do_not_execute_python_capability():
    calls = []
    credential = Credential(
        key_id="go-dev-key", peer_id="peer:go", principal_ref="principal:go",
        secret=SECRET, allowed_scopes=frozenset({"records:read"}),
    )
    peer = OBISPeer("peer:python", [credential])
    peer.register_capability(
        "records.read", "1.0", {"records:read"},
        lambda payload: calls.append(payload) or {"record_id": payload["record_id"]},
    )
    client = OBISClient(
        local_peer_id="peer:go", remote_peer_id="peer:python",
        key_id="go-dev-key", principal_ref="principal:go",
        secret=SECRET, scopes={"records:read"},
    )
    with OBISServer(peer) as server:
        malformed = client.build_request("records.read", "1.0", {"record_id": "bad-version"})
        malformed["version"] = "0.2"
        status, _ = _post_raw(server.address, malformed, sign_message(malformed, SECRET))
        assert status == 426

        unauthenticated = client.build_request("records.read", "1.0", {"record_id": "bad-signature"})
        status, _ = _post_raw(server.address, unauthenticated, "00" * 32)
        assert status == 401

    assert calls == []



def test_go_cli_durable_replay_survives_peer_process_restart(tmp_path):
    client = OBISClient(
        local_peer_id="peer:python",
        remote_peer_id="peer:go",
        key_id="python-dev-key",
        principal_ref="principal:python",
        secret=SECRET,
        scopes={"records:read"},
    )
    request = client.build_request("records.read", "1.0", {"record_id": "durable-replay"})
    signature = sign_message(request, SECRET)
    replay_dir = tmp_path / "go-replay-state"
    replay_dir.mkdir()

    first_process, first_endpoint = _start_go_server(replay_dir)
    try:
        first_status, _ = _post_raw(first_endpoint, request, signature)
        assert first_status == 200
    finally:
        first_process.terminate()
        first_process.wait(timeout=5)

    restarted_process, restarted_endpoint = _start_go_server(replay_dir)
    try:
        replay_status, _ = _post_raw(restarted_endpoint, request, signature)
        assert replay_status == 409
    finally:
        restarted_process.terminate()
        restarted_process.wait(timeout=5)



def test_go_cli_replay_storage_failure_returns_signed_503_before_execution(tmp_path):
    replay_dir = tmp_path / "go-replay-state-unavailable"
    replay_dir.mkdir()
    process, endpoint = _start_go_server(replay_dir)
    try:
        replay_dir.rmdir()
        client = OBISClient(
            local_peer_id="peer:python",
            remote_peer_id="peer:go",
            key_id="python-dev-key",
            principal_ref="principal:python",
            secret=SECRET,
            scopes={"records:read"},
        )
        with pytest.raises(OBISRequestError) as raised:
            client.invoke(endpoint, "records.read", "1.0", {"record_id": "storage-failure"})
        assert raised.value.code == "replay.storage_unavailable"
        assert raised.value.http_status == 503
    finally:
        process.terminate()
        process.wait(timeout=5)

def test_python_to_go_authenticated_negative_request_matrix():
    process, endpoint = _start_go_server()
    try:
        client = OBISClient(
            local_peer_id="peer:python", remote_peer_id="peer:go",
            key_id="python-dev-key", principal_ref="principal:python",
            secret=SECRET, scopes={"records:read"},
        )

        expired = client.build_request("records.read", "1.0", {"record_id": "expired"})
        now = int(__import__("time").time())
        expired["issued_at"] = now - 60
        expired["expires_at"] = now - 30
        status, _ = _post_raw(endpoint, expired, sign_message(expired, SECRET))
        assert status == 408

        unknown_top_level = client.build_request(
            "records.read", "1.0", {"record_id": "unknown-top-level"}
        )
        unknown_top_level["unexpected"] = "outside-contract"
        status, _ = _post_raw(
            endpoint, unknown_top_level, sign_message(unknown_top_level, SECRET)
        )
        assert status == 400

        unknown_nested = client.build_request(
            "records.read", "1.0", {"record_id": "unknown-nested"}
        )
        unknown_nested["sender"]["bridge_id"] = "outside-contract"
        status, _ = _post_raw(
            endpoint, unknown_nested, sign_message(unknown_nested, SECRET)
        )
        assert status == 400

        status, _ = _post_raw_bytes(endpoint, b"{")
        assert status == 400

        status, _ = _post_raw_bytes(
            endpoint, b'{"protocol":"obis","protocol":"obis"}'
        )
        assert status == 400
    finally:
        process.terminate()
        process.wait(timeout=5)




def test_python_to_go_authenticated_error_responses_are_signed_and_bound():
    process, endpoint = _start_go_server()
    try:
        client = OBISClient(
            local_peer_id="peer:python", remote_peer_id="peer:go",
            key_id="python-dev-key", principal_ref="principal:python",
            secret=SECRET, scopes={"records:read", "records:write"},
        )

        expired = client.build_request("records.read", "1.0", {"record_id": "expired-signed-error"})
        now = int(__import__("time").time())
        expired["issued_at"] = now - 60
        expired["expires_at"] = now - 30
        status, body, response_signature = _post_raw_with_headers(
            endpoint, expired, sign_message(expired, SECRET)
        )
        _assert_signed_error_response(
            expired, status, body, response_signature, 408, "request.expired"
        )

        unsupported = client.build_request(
            "records.read", "1.0", {"record_id": "unsupported-version-signed-error"}
        )
        unsupported["version"] = "0.2"
        status, body, response_signature = _post_raw_with_headers(
            endpoint, unsupported, sign_message(unsupported, SECRET)
        )
        _assert_signed_error_response(
            unsupported, status, body, response_signature, 426, "protocol.unsupported_version"
        )

        missing_capability = client.build_request(
            "missing.capability", "1.0", {"record_id": "missing-capability-signed-error"}
        )
        status, body, response_signature = _post_raw_with_headers(
            endpoint, missing_capability, sign_message(missing_capability, SECRET)
        )
        _assert_signed_error_response(
            missing_capability, status, body, response_signature, 404, "capability.unknown"
        )

        denied_scope = client.build_request(
            "records.read", "1.0", {"record_id": "scope-denial-signed-error"},
            scopes={"records:write"},
        )
        status, body, response_signature = _post_raw_with_headers(
            endpoint, denied_scope, sign_message(denied_scope, SECRET)
        )
        _assert_signed_error_response(
            denied_scope, status, body, response_signature, 403, "authorization.denied"
        )

        replay = client.build_request(
            "records.read", "1.0", {"record_id": "replay-signed-error"},
            scopes={"records:read"},
        )
        replay_signature = sign_message(replay, SECRET)
        first_status, _, _ = _post_raw_with_headers(endpoint, replay, replay_signature)
        assert first_status == 200
        status, body, response_signature = _post_raw_with_headers(
            endpoint, replay, replay_signature
        )
        _assert_signed_error_response(
            replay, status, body, response_signature, 409, "request.replay_detected"
        )
    finally:
        process.terminate()
        process.wait(timeout=5)


def _start_go_v02_server(tmp_path):
    command = [
        GO_PEER_BINARY, "server-v02",
        "--peer-id", "peer:go-v02",
        "--listen", "127.0.0.1:0",
        "--key-id", "python-v02-key",
        "--remote-peer", "peer:python",
        "--principal", "principal:python",
        "--secret-hex", SECRET.hex(),
        "--scopes", "inventory.read",
        "--ledger-path", str(tmp_path / "go-operations.json"),
        "--allowed-resource", "project-a/source-a",
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert process.stdout is not None
    address = process.stdout.readline().strip()
    if not address:
        stderr = process.stderr.read() if process.stderr else ""
        process.kill()
        raise AssertionError(f"Go OBIS 0.2 peer did not publish its loopback address: {stderr}")
    return process, f"http://{address}"


def test_python_v02_client_invokes_go_v02_peer_and_queries_status(tmp_path):
    from obis_bridge import Credential
    from obis_bridge.v02 import OBISV02Client

    process, endpoint = _start_go_v02_server(tmp_path)
    try:
        client = OBISV02Client(
            "peer:python", "peer:go-v02", "python-v02-key",
            "principal:python", SECRET, {"inventory.read"},
        )
        first = client.invoke(
            endpoint, "ecoscan.inventory.read", "1.0",
            {"project_id": "project-a", "source_id": "source-a", "measurement_kinds": ["logical_bytes", "file_count"]},
            operation_id="cross-op-1", idempotency_key="cross-idem-1",
        )
        second = client.invoke(
            endpoint, "ecoscan.inventory.read", "1.0",
            {"project_id": "project-a", "source_id": "source-a", "measurement_kinds": ["logical_bytes", "file_count"]},
            operation_id="cross-op-1", idempotency_key="cross-idem-1",
        )
        status = client.status(
            endpoint, "ecoscan.inventory.read", "1.0", "cross-op-1",
            resource={"project_id": "project-a", "source_id": "source-a", "measurement_kinds": ["logical_bytes", "file_count"]},
        )
        assert first["operation"]["state"] == "SUCCEEDED"
        assert second["operation"]["result"] == first["operation"]["result"]
        assert status["operation"]["state"] == "SUCCEEDED"
        assert first["operation"]["result"]["items_seen"] == 2
        assert first["operation"]["result"]["source_id"] == "source-a"
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_go_v02_client_invokes_python_v02_peer(tmp_path):
    from obis_bridge import Credential
    from obis_bridge.operations import OperationLedger
    from obis_bridge.peer import OBISPeer
    from obis_bridge.v02 import OBISPeerV02, OBISV02Server

    credential = Credential(
        key_id="go-v02-key", peer_id="peer:go", principal_ref="principal:go",
        secret=SECRET, allowed_scopes=frozenset({"inventory.read"}),
        allowed_resources=frozenset({("project-b", "source-b")}),
    )
    peer = OBISPeer("peer:python-v02", [credential])
    calls = []
    peer_v02 = OBISPeerV02(peer, OperationLedger(tmp_path / "python-operations.sqlite3"))
    peer_v02.register_capability(
        "ecoscan.inventory.read", "1.0", {"inventory.read"},
        lambda payload: calls.append(payload) or {
            "items_seen": 1, "source_id": payload["source_id"], "served_by": "python-peer-v02",
        },
        recovery_class="IDEMPOTENT", resource_binding=True,
    )
    with OBISV02Server(peer_v02) as server:
        result = subprocess.run(
            [
                GO_PEER_BINARY, "invoke-v02",
                "--endpoint", server.address,
                "--local-peer", "peer:go",
                "--remote-peer", "peer:python-v02",
                "--key-id", "go-v02-key",
                "--principal", "principal:go",
                "--secret-hex", SECRET.hex(),
                "--scopes", "inventory.read",
                "--capability", "ecoscan.inventory.read",
                "--capability-version", "1.0",
                "--operation-id", "go-cross-op-1",
                "--idempotency-key", "go-cross-idem-1",
                "--payload", json.dumps({"project_id": "project-b", "source_id": "source-b"}),
            ],
            capture_output=True, text=True, timeout=15,
        )
    assert result.returncode == 0, result.stdout + result.stderr
    response = json.loads(result.stdout)
    assert response["state"] == "SUCCEEDED"
    assert response["result"]["served_by"] == "python-peer-v02"
    assert len(calls) == 1
