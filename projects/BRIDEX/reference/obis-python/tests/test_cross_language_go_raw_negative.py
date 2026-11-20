import os
import subprocess
from pathlib import Path

from obis_bridge import Credential, OBISPeer, OBISServer


def test_go_signed_raw_negative_requests_are_rejected_by_python_peer():
    go_root = Path(__file__).resolve().parents[2] / "obis-go"
    if not (go_root / "go.mod").is_file():
        import pytest
        pytest.skip("independent Go reference peer source is unavailable")

    calls = []
    secret = b"0123456789abcdef0123456789abcdef"
    credential = Credential(
        key_id="go-dev-key",
        peer_id="peer:go",
        principal_ref="principal:go",
        secret=secret,
        allowed_scopes=frozenset({"records:read"}),
    )
    peer = OBISPeer("peer:python", [credential])
    peer.register_capability(
        "records.read",
        "1.0",
        {"records:read"},
        lambda payload: calls.append(payload) or {"record_id": payload["record_id"]},
    )

    with OBISServer(peer) as server:
        env = os.environ.copy()
        env["OBIS_PYTHON_PEER_ENDPOINT"] = server.address
        result = subprocess.run(
            ["go", "test", "./obis", "-run", "^TestGoRawNegativeRequestsToPythonPeer$", "-count=1"],
            cwd=go_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    assert result.returncode == 0, result.stdout + result.stderr
    assert calls == []
