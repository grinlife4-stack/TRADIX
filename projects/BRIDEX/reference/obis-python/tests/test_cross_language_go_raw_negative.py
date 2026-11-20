import os
import shutil
import subprocess
import sys
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


def test_go_request_replay_is_rejected_after_python_peer_process_restart(tmp_path):
    if shutil.which("go") is None:
        import pytest
        pytest.skip("Go toolchain is required for the independent-peer integration test")

    go_root = Path(__file__).resolve().parents[2] / "obis-go"
    if not (go_root / "go.mod").is_file():
        import pytest
        pytest.skip("independent Go reference peer source is unavailable")

    database_path = tmp_path / "python-peer-replay.sqlite3"
    counter_path = tmp_path / "capability-calls.log"
    server_script = """
import os
import sys
import time
from obis_bridge import Credential, OBISPeer, OBISServer
from obis_bridge.peer import SQLiteReplayGuard

database_path, counter_path = sys.argv[1], sys.argv[2]
secret = b"0123456789abcdef0123456789abcdef"
credential = Credential(
    key_id="go-dev-key",
    peer_id="peer:go",
    principal_ref="principal:go",
    secret=secret,
    allowed_scopes=frozenset({"records:read"}),
)
peer = OBISPeer(
    "peer:python",
    [credential],
    replay_guard=SQLiteReplayGuard(database_path),
)

def handle(payload):
    with open(counter_path, "a", encoding="utf-8") as counter:
        counter.write("called" + chr(10))
        counter.flush()
        os.fsync(counter.fileno())
    return {"record_id": payload["record_id"], "served_by": "python-peer"}

peer.register_capability("records.read", "1.0", {"records:read"}, handle)
server = OBISServer(peer).start()
print(server.address, flush=True)
while True:
    time.sleep(1)
"""

    def start_python_peer():
        process = subprocess.Popen(
            [sys.executable, "-c", server_script, str(database_path), str(counter_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert process.stdout is not None
        endpoint = process.stdout.readline().strip()
        if not endpoint:
            process.kill()
            _, stderr = process.communicate(timeout=5)
            raise AssertionError(f"Python peer did not publish its endpoint: {stderr}")
        return process, endpoint

    def stop_python_peer(process):
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    def run_go_request(endpoint, expected_status):
        env = os.environ.copy()
        env["OBIS_PYTHON_PEER_ENDPOINT"] = endpoint
        env["OBIS_EXPECTED_HTTP_STATUS"] = str(expected_status)
        result = subprocess.run(
            [
                "go", "test", "./obis",
                "-run", "^TestGoDurableReplayRequestToPythonPeer$",
                "-count=1",
            ],
            cwd=go_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    first_process, first_endpoint = start_python_peer()
    try:
        run_go_request(first_endpoint, 200)
    finally:
        stop_python_peer(first_process)

    assert counter_path.read_text(encoding="utf-8").splitlines() == ["called"]

    restarted_process, restarted_endpoint = start_python_peer()
    try:
        run_go_request(restarted_endpoint, 409)
    finally:
        stop_python_peer(restarted_process)

    assert counter_path.read_text(encoding="utf-8").splitlines() == ["called"]
