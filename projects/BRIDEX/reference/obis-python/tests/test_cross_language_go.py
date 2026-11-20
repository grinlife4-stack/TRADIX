import json
import os
import subprocess
import urllib.error
import urllib.request

import pytest

from obis_bridge import OBISClient, OBISPeer, OBISServer, Credential, OBISRequestError
from obis_bridge.peer import canonical_json, sign_message


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
    credential = Credential(
        key_id="go-dev-key",
        peer_id="peer:go",
        principal_ref="principal:go",
        secret=SECRET,
        allowed_scopes=frozenset({"records:read"}),
    )
    peer = OBISPeer("peer:python", [credential])
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
                "--payload", json.dumps({"record_id": "missing"}),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    assert result.returncode != 0
    assert "capability.unknown" in result.stderr


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
        lambda payload: {"record_id": payload["record_id"]},
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



def _post_raw(endpoint, message, signature):
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
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()



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

