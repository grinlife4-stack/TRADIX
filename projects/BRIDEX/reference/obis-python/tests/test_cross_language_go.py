import json
import os
import subprocess

import pytest

from obis_bridge import OBISClient, OBISPeer, OBISServer, Credential, OBISRequestError, OBISRequestError


GO_PEER_BINARY = os.environ.get("OBIS_GO_PEER_BINARY")
SECRET = b"0123456789abcdef0123456789abcdef"


pytestmark = pytest.mark.skipif(
    not GO_PEER_BINARY or not os.path.isfile(GO_PEER_BINARY),
    reason="independent Go peer binary is built by the repository CI workflow",
)


def _start_go_server():
    process = subprocess.Popen(
        [
            GO_PEER_BINARY,
            "--peer-id", "peer:go",
            "--listen", "127.0.0.1:0",
            "--key-id", "python-dev-key",
            "--remote-peer", "peer:python",
            "--principal", "principal:python",
            "--secret-hex", SECRET.hex(),
            "--scopes", "records:read",
        ],
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
