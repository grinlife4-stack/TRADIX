from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

import pytest

from obis_bridge import Credential, OBISClient, OBISPeer, OBISRequestError, OBISServer
from test_tls_transport import client_context, create_ca, create_leaf, server_context


PYTHON_URI = "urn:obis:peer:11111111-1111-4111-8111-111111111111"
GO_URI = "urn:obis:peer:22222222-2222-4222-8222-222222222222"
OTHER_GO_URI = "urn:obis:peer:33333333-3333-4333-8333-333333333333"
CAPABILITY = "catalog.lookup"
CAPABILITY_VERSION = "1.0"


def _free_loopback_address() -> str:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return f"127.0.0.1:{listener.getsockname()[1]}"


def _start_go_peer(environment: dict[str, str]) -> subprocess.Popen:
    go_project = Path(__file__).parents[2] / "obis-go"
    return subprocess.Popen(
        ["go", "run", "./cmd/obis-go-peer"],
        cwd=go_project,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )


def _wait_for_go_peer(process: subprocess.Popen, url: str, *, context=None) -> None:
    last_error = None
    for _ in range(300):
        if process.poll() is not None:
            stderr = process.stderr.read() if process.stderr else ""
            raise AssertionError(f"Go OBIS peer exited before startup: {stderr}")
        try:
            with urllib.request.urlopen(url, context=context, timeout=0.5) as response:
                if response.status == 204:
                    return
        except Exception as exc:
            last_error = repr(exc)
            time.sleep(0.1)
    raise AssertionError(f"Go OBIS peer did not become ready: {last_error}")


@pytest.mark.skipif(shutil.which("go") is None, reason="Go toolchain is required for cross-language conformance")
def test_python_hmac_development_client_interoperates_with_go_peer() -> None:
    secret = b"0123456789abcdef0123456789abcdef"
    address = _free_loopback_address()
    environment = os.environ.copy()
    environment.update({"OBIS_TEST_SECRET": secret.decode("ascii"), "OBIS_LISTEN_ADDR": address})
    process = _start_go_peer(environment)
    try:
        _wait_for_go_peer(process, f"http://{address}/healthz")
        client = OBISClient(
            local_peer_id="python-peer",
            remote_peer_id="go-peer",
            key_id="python-key",
            principal_ref="principal:python",
            secret=secret,
            scopes={"catalog:read"},
            timeout=3.0,
        )
        response = client.invoke(
            f"http://{address}", CAPABILITY, CAPABILITY_VERSION, {"item_id": "sample-bridge"}
        )
        assert response["outcome"] == "succeeded"
        assert response["result"] == {
            "accepted": True,
            "item_id": "sample-bridge",
            "served_by": "go-peer",
        }
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@pytest.mark.skipif(shutil.which("go") is None, reason="Go toolchain is required for cross-language mTLS conformance")
def test_python_mtls_client_interoperates_with_go_mtls_server_without_hmac(tmp_path: Path) -> None:
    ca_key, ca_cert, ca_path = create_ca(tmp_path)
    _, server_cert, server_key, _ = create_leaf(
        tmp_path, ca_key, ca_cert, GO_URI, server=True, filename="go-server"
    )
    _, client_cert, client_key, client_fingerprint = create_leaf(
        tmp_path, ca_key, ca_cert, PYTHON_URI, server=False, filename="python-client"
    )
    address = _free_loopback_address()
    environment = os.environ.copy()
    environment.update({
        "OBIS_LISTEN_ADDR": address,
        "OBIS_SERVER_PEER_ID": GO_URI,
        "OBIS_CLIENT_PEER_ID": PYTHON_URI,
        "OBIS_CLIENT_CERT_URI": PYTHON_URI,
        "OBIS_CLIENT_CERT_SHA256": client_fingerprint,
        "OBIS_CLIENT_KEY_ID": "python-certificate",
        "OBIS_CLIENT_PRINCIPAL": "principal:python",
        "OBIS_CLIENT_SCOPES": "catalog:read",
        "OBIS_TLS_CERT": str(server_cert),
        "OBIS_TLS_KEY": str(server_key),
        "OBIS_TLS_CA": str(ca_path),
    })
    process = _start_go_peer(environment)
    tls_context = client_context(ca_path, client_cert, client_key)
    try:
        _wait_for_go_peer(process, f"https://{address}/healthz", context=tls_context)
        client = OBISClient(
            PYTHON_URI,
            GO_URI,
            "python-certificate",
            "principal:python",
            None,
            {"catalog:read"},
            timeout=3.0,
            tls_context=tls_context,
        )
        response = client.invoke(
            f"https://{address}", CAPABILITY, CAPABILITY_VERSION, {"item_id": "python-to-go-mtls"}
        )
        assert response["outcome"] == "succeeded"
        assert response["result"]["served_by"] == "go-peer"
        assert response["result"]["item_id"] == "python-to-go-mtls"
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@pytest.mark.skipif(shutil.which("go") is None, reason="Go toolchain is required for cross-language mTLS conformance")
def test_go_mtls_client_interoperates_with_python_mtls_server_without_hmac(tmp_path: Path) -> None:
    ca_key, ca_cert, ca_path = create_ca(tmp_path)
    _, server_cert, server_key, _ = create_leaf(
        tmp_path, ca_key, ca_cert, PYTHON_URI, server=True, filename="python-server"
    )
    _, client_cert, client_key, client_fingerprint = create_leaf(
        tmp_path, ca_key, ca_cert, GO_URI, server=False, filename="go-client"
    )
    python_peer = OBISPeer(
        PYTHON_URI,
        [Credential(
            key_id="go-certificate",
            peer_id=GO_URI,
            principal_ref="principal:go",
            secret=None,
            allowed_scopes=frozenset({"catalog:read"}),
            certificate_uri=GO_URI,
            certificate_sha256=client_fingerprint,
        )],
    )
    python_peer.register_capability(
        CAPABILITY,
        CAPABILITY_VERSION,
        {"catalog:read"},
        lambda payload: {
            "accepted": True,
            "item_id": payload["item_id"],
            "served_by": "python-peer",
        },
    )
    tls_server = server_context(ca_path, server_cert, server_key)
    environment = os.environ.copy()
    environment.update({
        "OBIS_REMOTE_ENDPOINT": "",
        "OBIS_LOCAL_PEER_ID": GO_URI,
        "OBIS_REMOTE_PEER_ID": PYTHON_URI,
        "OBIS_KEY_ID": "go-certificate",
        "OBIS_PRINCIPAL_REF": "principal:go",
        "OBIS_TLS_CA": str(ca_path),
        "OBIS_TLS_CERT": str(client_cert),
        "OBIS_TLS_KEY": str(client_key),
        "OBIS_TLS_SERVER_NAME": "127.0.0.1",
        "OBIS_TEST_ITEM_ID": "go-to-python-mtls",
    })
    go_project = Path(__file__).parents[2] / "obis-go"
    with OBISServer(python_peer, tls_context=tls_server) as server:
        environment["OBIS_REMOTE_ENDPOINT"] = server.address
        completed = subprocess.run(
            ["go", "run", "./cmd/obis-go-client"],
            cwd=go_project,
            env=environment,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    assert completed.returncode == 0, completed.stderr
    response = json.loads(completed.stdout)
    assert response["outcome"] == "succeeded"
    assert response["sender"]["peer_id"] == PYTHON_URI
    assert response["result"]["served_by"] == "python-peer"
    assert response["result"]["item_id"] == "go-to-python-mtls"


@pytest.mark.skipif(shutil.which("go") is None, reason="Go toolchain is required for cross-language mTLS conformance")
def test_go_mtls_server_rejects_wrong_certificate_fingerprint(tmp_path: Path) -> None:
    ca_key, ca_cert, ca_path = create_ca(tmp_path)
    _, server_cert, server_key, _ = create_leaf(
        tmp_path, ca_key, ca_cert, GO_URI, server=True, filename="go-server"
    )
    _, expected_cert, _, expected_fingerprint = create_leaf(
        tmp_path, ca_key, ca_cert, PYTHON_URI, server=False, filename="expected-client"
    )
    _, wrong_cert, wrong_key, _ = create_leaf(
        tmp_path, ca_key, ca_cert, PYTHON_URI, server=False, filename="wrong-client"
    )
    address = _free_loopback_address()
    environment = os.environ.copy()
    environment.update({
        "OBIS_LISTEN_ADDR": address,
        "OBIS_SERVER_PEER_ID": GO_URI,
        "OBIS_CLIENT_PEER_ID": PYTHON_URI,
        "OBIS_CLIENT_CERT_URI": PYTHON_URI,
        "OBIS_CLIENT_CERT_SHA256": expected_fingerprint,
        "OBIS_CLIENT_KEY_ID": "python-certificate",
        "OBIS_CLIENT_PRINCIPAL": "principal:python",
        "OBIS_CLIENT_SCOPES": "catalog:read",
        "OBIS_TLS_CERT": str(server_cert),
        "OBIS_TLS_KEY": str(server_key),
        "OBIS_TLS_CA": str(ca_path),
    })
    process = _start_go_peer(environment)
    tls_context = client_context(ca_path, wrong_cert, wrong_key)
    try:
        _wait_for_go_peer(process, f"https://{address}/healthz", context=tls_context)
        client = OBISClient(
            PYTHON_URI,
            GO_URI,
            "python-certificate",
            "principal:python",
            None,
            {"catalog:read"},
            timeout=3.0,
            tls_context=tls_context,
        )
        with pytest.raises(OBISRequestError):
            client.invoke(
                f"https://{address}", CAPABILITY, CAPABILITY_VERSION, {"item_id": "must-be-rejected"}
            )
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
