from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

import pytest

from obis_bridge import (Credential, OBISClient, OBISPeer, OBISServer, create_tls13_client_context, create_tls13_server_context)


@pytest.mark.skipif(shutil.which("go") is None, reason="Go toolchain is required for cross-language conformance")
def test_python_client_interoperates_with_independent_go_obis_peer() -> None:
    repository = Path(__file__).parents[2]
    go_project = repository / "obis-go"
    secret = b"0123456789abcdef0123456789abcdef"
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    address = f"127.0.0.1:{port}"
    environment = os.environ.copy()
    environment["OBIS_TEST_SECRET"] = secret.decode("ascii")
    environment["OBIS_LISTEN_ADDR"] = address
    process = subprocess.Popen(
        ["go", "run", "./cmd/obis-go-peer"],
        cwd=go_project,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        health_url = f"http://{address}/healthz"
        ready = False
        for _ in range(150):
            if process.poll() is not None:
                stderr = process.stderr.read() if process.stderr else ""
                raise AssertionError(f"Go OBIS peer exited before startup: {stderr}")
            try:
                with urllib.request.urlopen(health_url, timeout=0.25) as response:
                    ready = response.status == 204
                    if ready:
                        break
            except Exception:
                time.sleep(0.1)
        assert ready, "Go OBIS peer did not become ready"

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
            f"http://{address}",
            "catalog.lookup",
            "1.0",
            {"item_id": "sample-bridge"},
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


@pytest.mark.skipif(
    shutil.which("go") is None or shutil.which("openssl") is None,
    reason="Go and OpenSSL are required for TLS 1.3 mTLS conformance",
)
def test_python_client_interoperates_with_go_peer_over_tls13_mtls(tmp_path: Path) -> None:
    secret = b"0123456789abcdef0123456789abcdef"
    ca_key, ca_cert = tmp_path / "ca.key", tmp_path / "ca.crt"
    server_key, server_csr, server_cert = tmp_path / "server.key", tmp_path / "server.csr", tmp_path / "server.crt"
    client_key, client_csr, client_cert = tmp_path / "client.key", tmp_path / "client.csr", tmp_path / "client.crt"
    server_ext, client_ext = tmp_path / "server.ext", tmp_path / "client.ext"

    commands = [
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-sha256", "-days", "1", "-nodes",
         "-keyout", str(ca_key), "-out", str(ca_cert), "-subj", "/CN=OBIS-Test-CA"],
        ["openssl", "req", "-newkey", "rsa:2048", "-nodes", "-keyout", str(server_key),
         "-out", str(server_csr), "-subj", "/CN=OBIS-Go-Peer"],
        ["openssl", "x509", "-req", "-in", str(server_csr), "-CA", str(ca_cert), "-CAkey", str(ca_key),
         "-CAcreateserial", "-out", str(server_cert), "-days", "1", "-sha256", "-extfile", str(server_ext)],
        ["openssl", "req", "-newkey", "rsa:2048", "-nodes", "-keyout", str(client_key),
         "-out", str(client_csr), "-subj", "/CN=OBIS-Python-Peer"],
        ["openssl", "x509", "-req", "-in", str(client_csr), "-CA", str(ca_cert), "-CAkey", str(ca_key),
         "-CAserial", str(tmp_path / "ca.srl"), "-out", str(client_cert), "-days", "1", "-sha256", "-extfile", str(client_ext)],
    ]
    server_ext.write_text(
        "basicConstraints=CA:FALSE\nkeyUsage=digitalSignature\nextendedKeyUsage=serverAuth\n"
        "subjectAltName=IP:127.0.0.1,URI:urn:obis:peer:go-peer\n",
        encoding="utf-8",
    )
    client_ext.write_text(
        "basicConstraints=CA:FALSE\nkeyUsage=digitalSignature\nextendedKeyUsage=clientAuth\n"
        "subjectAltName=URI:urn:obis:peer:python-peer\n",
        encoding="utf-8",
    )
    for command in commands:
        completed = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, timeout=20, check=False)
        assert completed.returncode == 0, completed.stderr

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    address = f"127.0.0.1:{port}"
    environment = os.environ.copy()
    environment.update({
        "OBIS_TEST_SECRET": secret.decode("ascii"),
        "OBIS_LISTEN_ADDR": address,
        "OBIS_TLS_CERT": str(server_cert),
        "OBIS_TLS_KEY": str(server_key),
        "OBIS_TLS_CA": str(ca_cert),
    })
    process = subprocess.Popen(
        ["go", "run", "./cmd/obis-go-peer"],
        cwd=Path(__file__).parents[2] / "obis-go",
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        health_url = f"https://127.0.0.1:{port}/healthz"
        client_context = create_tls13_client_context(str(ca_cert), str(client_cert), str(client_key))
        ready = False
        last_error = None
        for _ in range(150):
            if process.poll() is not None:
                stderr = process.stderr.read() if process.stderr else ""
                raise AssertionError(f"TLS Go OBIS peer exited before startup: {stderr}")
            try:
                with urllib.request.urlopen(health_url, context=client_context, timeout=0.5) as response:
                    ready = response.status == 204
                    if ready:
                        break
            except Exception as exc:
                last_error = repr(exc)
                time.sleep(0.1)
        assert ready, f"TLS Go OBIS peer did not become ready: {last_error}"

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
            f"https://127.0.0.1:{port}",
            "catalog.lookup",
            "1.0",
            {"item_id": "tls-mtls-sample"},
            ssl_context=client_context,
        )
        assert response["outcome"] == "succeeded"
        assert response["result"]["served_by"] == "go-peer"
        assert response["result"]["item_id"] == "tls-mtls-sample"

        python_peer = OBISPeer(
            "go-peer",
            [Credential(
                key_id="python-key",
                peer_id="python-peer",
                principal_ref="principal:python",
                secret=secret,
                allowed_scopes=frozenset({"catalog:read"}),
            )],
        )
        python_peer.register_capability(
            "catalog.lookup", "1.0", {"catalog:read"},
            lambda payload: {"accepted": True, "item_id": payload["item_id"], "served_by": "python-peer"},
        )
        server_context = create_tls13_server_context(str(server_cert), str(server_key), str(ca_cert))
        with OBISServer(python_peer, ssl_context=server_context) as python_server:
            python_response = client.invoke(
                python_server.address,
                "catalog.lookup",
                "1.0",
                {"item_id": "tls-python-server"},
                ssl_context=client_context,
            )
        assert python_response["result"]["served_by"] == "python-peer"
        assert python_response["result"]["item_id"] == "tls-python-server"
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
