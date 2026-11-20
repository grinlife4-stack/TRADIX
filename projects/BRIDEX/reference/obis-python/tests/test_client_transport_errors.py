import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from obis_bridge import OBISClient, OBISRequestError


SECRET = b"0123456789abcdef0123456789abcdef"


def _client(timeout=0.05):
    return OBISClient(
        local_peer_id="peer:local",
        remote_peer_id="peer:remote",
        key_id="test-key",
        principal_ref="principal:local",
        secret=SECRET,
        scopes={"records:read"},
        timeout=timeout,
    )


def test_python_client_classifies_transport_timeout_separately():
    release = threading.Event()

    class SlowHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            release.wait(timeout=1)
            self.send_response(200)
            self.end_headers()

        def log_message(self, fmt, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), SlowHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(OBISRequestError) as raised:
            _client(timeout=0.05).invoke(
                f"http://127.0.0.1:{server.server_port}",
                "records.read",
                "1.0",
                {"record_id": "timeout"},
            )
        assert raised.value.code == "peer.timeout"
        assert raised.value.http_status == 504
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_python_client_classifies_connection_failure_separately():
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    endpoint_port = listener.getsockname()[1]
    listener.close()

    with pytest.raises(OBISRequestError) as raised:
        _client(timeout=0.5).invoke(
            f"http://127.0.0.1:{endpoint_port}",
            "records.read",
            "1.0",
            {"record_id": "unavailable"},
        )
    assert raised.value.code == "peer.unavailable"
    assert raised.value.http_status == 503

def test_python_client_enforces_absolute_deadline_against_slow_drip_response():
    class SlowDripHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/obis+json")
            self.send_header("Content-Length", "20")
            self.end_headers()
            for _ in range(20):
                try:
                    self.wfile.write(b"x")
                    self.wfile.flush()
                except OSError:
                    return
                time.sleep(0.02)

        def log_message(self, fmt, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), SlowDripHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    started = time.monotonic()
    try:
        with pytest.raises(OBISRequestError) as raised:
            _client(timeout=1.0).invoke(
                f"http://127.0.0.1:{server.server_port}",
                "records.read",
                "1.0",
                {"record_id": "slow-drip"},
                deadline=time.monotonic() + 0.12,
            )
        elapsed = time.monotonic() - started
        assert raised.value.code == "peer.timeout"
        assert raised.value.http_status == 504
        assert elapsed < 0.5
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

def test_python_client_does_not_open_socket_for_already_expired_deadline():
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    listener.settimeout(0.05)
    endpoint_port = listener.getsockname()[1]
    try:
        with pytest.raises(OBISRequestError) as raised:
            _client(timeout=1.0).invoke(
                f"http://127.0.0.1:{endpoint_port}",
                "records.read",
                "1.0",
                {"record_id": "expired-before-connect"},
                deadline=time.monotonic() - 1,
            )
        assert raised.value.code == "peer.timeout"
        assert raised.value.http_status == 504
        with pytest.raises(socket.timeout):
            listener.accept()
    finally:
        listener.close()

