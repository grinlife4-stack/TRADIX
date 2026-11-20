import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from obis_bridge import OBISClient, OBISRequestError
from obis_bridge.peer import canonical_json, sign_message


SECRET = b"0123456789abcdef0123456789abcdef"


def _signed_response_server(status, mutate=None):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            response = {
                "protocol": "obis",
                "version": "0.1",
                "message_type": "response",
                "message_id": "python-response-test",
                "correlation_id": request["message_id"],
                "sender": {"peer_id": "peer:remote"},
                "recipient": {"peer_id": "peer:local"},
                "issued_at": time.time(),
                "outcome": "succeeded" if status == 200 else "failed",
            }
            if status == 200:
                response["result"] = {"accepted": True}
            else:
                response["error"] = {"code": "authorization.denied", "message": "denied"}
            if mutate is not None:
                mutate(response)
            body = canonical_json(response)
            signature = sign_message(response, SECRET)
            self.send_response(status)
            self.send_header("Content-Type", "application/obis+json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-OBIS-Signature", signature)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _client():
    return OBISClient(
        local_peer_id="peer:local",
        remote_peer_id="peer:remote",
        key_id="test-key",
        principal_ref="principal:local",
        secret=SECRET,
        scopes={"records:read"},
    )


@pytest.mark.parametrize(
    "name,mutate",
    [
        ("downgraded protocol version", lambda message: message.update(version="0.0")),
        ("wrong correlation id", lambda message: message.update(correlation_id="other-request")),
        ("wrong sender peer", lambda message: message.update(sender={"peer_id": "peer:attacker"})),
        ("unexpected response field", lambda message: message.update(extra="not-in-contract")),
    ],
)
def test_python_client_rejects_invalid_signed_success_responses(name, mutate):
    server, thread = _signed_response_server(200, mutate)
    try:
        with pytest.raises(OBISRequestError):
            _client().invoke(
                f"http://127.0.0.1:{server.server_port}",
                "records.read",
                "1.0",
                {"record_id": name},
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_python_client_rejects_malformed_signed_error_response():
    def mutate(response):
        response["error"]["unexpected"] = "not-allowed"

    server, thread = _signed_response_server(403, mutate)
    try:
        with pytest.raises(OBISRequestError):
            _client().invoke(
                f"http://127.0.0.1:{server.server_port}",
                "records.read",
                "1.0",
                {"record_id": "malformed-error"},
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
