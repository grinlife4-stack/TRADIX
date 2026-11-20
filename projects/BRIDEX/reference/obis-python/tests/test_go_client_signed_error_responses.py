import os
import subprocess

import pytest

from obis_bridge import Credential, OBISPeer, OBISServer


GO_PEER_BINARY = os.environ.get("OBIS_GO_PEER_BINARY")
SECRET = b"0123456789abcdef0123456789abcdef"

pytestmark = pytest.mark.skipif(
    not GO_PEER_BINARY or not os.path.isfile(GO_PEER_BINARY),
    reason="independent Go peer binary is built by the repository CI workflow",
)


@pytest.mark.parametrize(
    ("capability_id", "scopes", "expected_code"),
    [
        ("missing.capability", "records:read", "capability.unknown"),
        ("records.read", "records:write", "authorization.denied"),
    ],
)
def test_go_client_accepts_only_signed_correlated_python_error_responses(
    capability_id, scopes, expected_code
):
    executions = []
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
        lambda payload: executions.append(payload) or {"record_id": payload["record_id"]},
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
                "--scopes", scopes,
                "--capability", capability_id,
                "--capability-version", "1.0",
                "--payload", '{"record_id":"signed-error-check"}',
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

    # Invoke returns the protocol error only after verifying the HMAC and
    # validating the response envelope, correlation ID, and both peer identities.
    assert result.returncode != 0
    assert expected_code in result.stderr
    assert executions == []
