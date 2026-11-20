from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

import pytest

from obis_bridge import Credential, OBISClient, OBISPeer, OBISRequestError, OBISServer
from obis_bridge.peer import MAX_TTL_SECONDS, canonical_json, sign_message, validate_request


SECRET = b"test-only-shared-secret-material-32-bytes-minimum"
KEY_ID = "test-peer-a-key"
PEER_A = "peer:independent-a"
PEER_B = "peer:independent-b"
PRINCIPAL_A = "principal:automation-a"


def make_pair():
    credential = Credential(
        key_id=KEY_ID,
        peer_id=PEER_A,
        principal_ref=PRINCIPAL_A,
        secret=SECRET,
        allowed_scopes=frozenset({"inventory:read"}),
    )
    peer_b = OBISPeer(PEER_B, [credential])
    peer_b.register_capability(
        "inventory.get",
        "1.0",
        {"inventory:read"},
        lambda payload: {"item_id": payload["item_id"], "available": True},
    )
    client = OBISClient(
        local_peer_id=PEER_A,
        remote_peer_id=PEER_B,
        key_id=KEY_ID,
        principal_ref=PRINCIPAL_A,
        secret=SECRET,
        scopes={"inventory:read"},
    )
    return peer_b, client


def test_two_independent_peers_exchange_direct_request_and_signed_response():
    peer_b, client = make_pair()
    with OBISServer(peer_b) as server:
        response = client.invoke(
            server.address,
            "inventory.get",
            "1.0",
            {"item_id": "sku-42"},
        )

    assert response["outcome"] == "succeeded"
    assert response["result"] == {"item_id": "sku-42", "available": True}
    assert response["sender"]["peer_id"] == PEER_B


def test_expired_request_is_rejected():
    peer_b, client = make_pair()
    request = client.build_request("inventory.get", "1.0", {"item_id": "x"}, now=time.time() - 120)
    with pytest.raises(OBISRequestError, match="expired"):
        validate_request(request)


def test_request_ttl_cannot_exceed_protocol_limit():
    peer_b, client = make_pair()
    request = client.build_request("inventory.get", "1.0", {"item_id": "x"})
    request["expires_at"] = request["issued_at"] + MAX_TTL_SECONDS + 1
    with pytest.raises(OBISRequestError, match="TTL"):
        validate_request(request)


def test_unknown_or_wrong_key_cannot_authenticate():
    peer_b, client = make_pair()
    request = client.build_request("inventory.get", "1.0", {"item_id": "x"})
    with pytest.raises(OBISRequestError, match="unknown credential"):
        peer_b.handle(request, "not-registered", sign_message(request, SECRET))


def test_credential_cannot_claim_another_peer_identity():
    peer_b, client = make_pair()
    request = client.build_request("inventory.get", "1.0", {"item_id": "x"})
    request["sender"]["peer_id"] = "peer:spoofed"
    with pytest.raises(OBISRequestError, match="signature verification"):
        peer_b.handle(request, KEY_ID, sign_message(
            {**request, "sender": {"peer_id": PEER_A}}, SECRET
        ))


def test_valid_identity_without_required_scope_is_denied():
    peer_b, client = make_pair()
    request = client.build_request(
        "inventory.get", "1.0", {"item_id": "x"}, scopes={"profile:read"}
    )
    with pytest.raises(OBISRequestError, match="required scope"):
        peer_b.handle(request, KEY_ID, sign_message(request, SECRET))


def test_capability_cannot_be_invoked_with_ungranted_scope():
    peer_b, client = make_pair()
    request = client.build_request(
        "inventory.get", "1.0", {"item_id": "x"},
        scopes={"inventory:read", "admin:all"},
    )
    with pytest.raises(OBISRequestError, match="exceeds grant"):
        peer_b.handle(request, KEY_ID, sign_message(request, SECRET))


def test_replayed_nonce_is_rejected():
    peer_b, client = make_pair()
    request = client.build_request("inventory.get", "1.0", {"item_id": "x"})
    signature = sign_message(request, SECRET)
    peer_b.handle(request, KEY_ID, signature)
    with pytest.raises(OBISRequestError, match="duplicate nonce"):
        peer_b.handle(request, KEY_ID, signature)


def test_wrong_recipient_is_rejected():
    peer_b, client = make_pair()
    request = client.build_request("inventory.get", "1.0", {"item_id": "x"})
    request["recipient"]["peer_id"] = "peer:other"
    with pytest.raises(OBISRequestError, match="signature verification"):
        peer_b.handle(request, KEY_ID, sign_message(
            {**request, "recipient": {"peer_id": PEER_B}}, SECRET
        ))


def test_unsupported_protocol_version_is_rejected():
    peer_b, client = make_pair()
    request = client.build_request("inventory.get", "1.0", {"item_id": "x"})
    request["version"] = "9.9"
    with pytest.raises(OBISRequestError, match="unsupported"):
        validate_request(request)


def test_missing_capability_is_rejected():
    peer_b, client = make_pair()
    request = client.build_request("admin.execute", "1.0", {"command": "whoami"})
    with pytest.raises(OBISRequestError, match="not registered"):
        peer_b.handle(request, KEY_ID, sign_message(request, SECRET))


def test_payload_size_is_bounded():
    peer_b, client = make_pair()
    request = client.build_request("inventory.get", "1.0", {"data": "x" * 70000})
    with pytest.raises(OBISRequestError, match="size limit"):
        validate_request(request)


def test_unknown_top_level_field_is_rejected():
    peer_b, client = make_pair()
    request = client.build_request("inventory.get", "1.0", {"item_id": "x"})
    request["unexpected"] = "must-not-be-accepted"
    with pytest.raises(OBISRequestError, match="unknown or missing"):
        validate_request(request)


def test_duplicate_authorization_scopes_are_rejected():
    peer_b, client = make_pair()
    request = client.build_request("inventory.get", "1.0", {"item_id": "x"})
    request["authorization"]["scopes"] = ["inventory:read", "inventory:read"]
    with pytest.raises(OBISRequestError, match="unique"):
        validate_request(request)


def test_capability_handler_failure_does_not_leak_exception_details():
    secret = SECRET
    credential = Credential(
        key_id=KEY_ID,
        peer_id=PEER_A,
        principal_ref=PRINCIPAL_A,
        secret=secret,
        allowed_scopes=frozenset({"inventory:read"}),
    )
    peer = OBISPeer(PEER_B, [credential])

    def broken_handler(payload):
        raise RuntimeError("sensitive internal path /srv/private/config")

    peer.register_capability("inventory.get", "1.0", {"inventory:read"}, broken_handler)
    client = OBISClient(PEER_A, PEER_B, KEY_ID, PRINCIPAL_A, secret, {"inventory:read"})
    request = client.build_request("inventory.get", "1.0", {"item_id": "x"})
    with pytest.raises(OBISRequestError) as exc:
        peer.handle(request, KEY_ID, sign_message(request, secret))
    assert exc.value.code == "operation.failed"
    assert "private" not in str(exc.value)
