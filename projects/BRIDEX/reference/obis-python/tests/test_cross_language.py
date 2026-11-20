from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

import pytest

from obis_bridge import OBISClient


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
