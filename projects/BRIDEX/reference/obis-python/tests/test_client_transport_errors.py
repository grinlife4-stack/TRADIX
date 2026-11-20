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
