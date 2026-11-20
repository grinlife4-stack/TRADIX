from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

import pytest

from obis_bridge import Credential, OBISClient, OBISPeer, OBISRequestError, OBISServer
from obis_bridge.peer import MAX_TTL_SECONDS, ReplayGuard, canonical_json, sign_message, strict_json_loads, validate_request, validate_response


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


def test_published_json_schema_validates_request_and_success_response():
    import json
    from importlib.resources import files
    from jsonschema import Draft202012Validator

    schema_path = files("obis_bridge").joinpath("schemas/message.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    peer_b, client = make_pair()
    request = client.build_request("inventory.get", "1.0", {"item_id": "sku-42"})
    validator.validate(request)

    response = {
        "protocol": "obis",
        "version": "0.1",
        "message_type": "response",
        "message_id": "response-1",
        "correlation_id": request["message_id"],
        "sender": {"peer_id": PEER_B},
        "recipient": {"peer_id": PEER_A},
        "issued_at": time.time(),
        "outcome": "succeeded",
        "result": {"available": True},
    }
    validator.validate(response)

    error_response = {
        "protocol": "obis",
        "version": "0.1",
        "message_type": "response",
        "message_id": "response-error-1",
        "correlation_id": request["message_id"],
        "sender": {"peer_id": PEER_B},
        "recipient": {"peer_id": PEER_A},
        "issued_at": time.time(),
        "outcome": "failed",
        "error": {"code": "authorization.denied", "message": "scope denied"},
    }
    validator.validate(error_response)


def test_published_json_schema_rejects_unknown_fields_and_invalid_error_envelope():
    import json
    from importlib.resources import files
    from jsonschema import Draft202012Validator, ValidationError

    schema_path = files("obis_bridge").joinpath("schemas/message.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)

    peer_b, client = make_pair()
    request = client.build_request("inventory.get", "1.0", {"item_id": "sku-42"})
    request["unexpected"] = True
    with pytest.raises(ValidationError):
        validator.validate(request)

    invalid_error = {
        "protocol": "obis",
        "version": "0.1",
        "message_type": "response",
        "message_id": "response-2",
        "correlation_id": "request-2",
        "sender": {"peer_id": PEER_B},
        "recipient": {"peer_id": PEER_A},
        "issued_at": time.time(),
        "outcome": "failed",
        "error": {"code": "authorization.denied"},
    }
    with pytest.raises(ValidationError):
        validator.validate(invalid_error)


def test_http_error_is_a_signed_correlated_obis_response():
    peer_b, client = make_pair()
    with OBISServer(peer_b) as server:
        with pytest.raises(OBISRequestError) as exc:
            client.invoke(
                server.address,
                "inventory.get",
                "1.0",
                {"item_id": "sku-42"},
                scopes={"profile:read"},
            )
    assert exc.value.code == "authorization.denied"
    assert "required scope" in str(exc.value)


def test_unknown_capability_returns_signed_correlated_obis_error():
    peer_b, client = make_pair()
    with OBISServer(peer_b) as server:
        with pytest.raises(OBISRequestError) as exc:
            client.invoke(server.address, "missing.capability", "1.0", {})
    assert exc.value.code == "capability.unknown"


def test_published_and_packaged_schemas_are_identical():
    from importlib.resources import files
    from pathlib import Path

    packaged = files("obis_bridge").joinpath("schemas/message.schema.json").read_bytes()
    canonical_path = Path(__file__).resolve().parents[5] / "standards" / "obis" / "0.1" / "message.schema.json"
    canonical = canonical_path.read_bytes()
    assert packaged == canonical


def test_duplicate_json_object_keys_are_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        strict_json_loads('{"protocol":"obis","protocol":"evil"}')


def test_replay_guard_is_atomic_under_concurrent_duplicate_requests():
    from concurrent.futures import ThreadPoolExecutor

    guard = ReplayGuard()
    with ThreadPoolExecutor(max_workers=16) as pool:
        outcomes = list(pool.map(lambda _: guard.accept("same-nonce", now=1000), range(64)))
    assert outcomes.count(True) == 1
    assert outcomes.count(False) == 63


def test_non_finite_and_negative_timestamps_are_rejected():
    peer_b, client = make_pair()
    request = client.build_request("inventory.get", "1.0", {"item_id": "x"})
    request["issued_at"] = float("nan")
    with pytest.raises(OBISRequestError, match="finite"):
        validate_request(request)

    request = client.build_request("inventory.get", "1.0", {"item_id": "x"})
    request["issued_at"] = -1
    with pytest.raises(OBISRequestError, match="non-negative"):
        validate_request(request)


def test_credential_repr_redacts_secret_and_freezes_scope_grants():
    mutable_scopes = {"inventory:read"}
    credential = Credential(
        key_id="key-redaction",
        peer_id=PEER_A,
        principal_ref=PRINCIPAL_A,
        secret=SECRET,
        allowed_scopes=mutable_scopes,
    )
    mutable_scopes.add("admin:all")
    assert credential.allowed_scopes == frozenset({"inventory:read"})
    assert SECRET.decode("utf-8") not in repr(credential)


def _valid_success_response(request):
    return {
        "protocol": "obis",
        "version": "0.1",
        "message_type": "response",
        "message_id": "response-valid",
        "correlation_id": request["message_id"],
        "sender": {"peer_id": PEER_B},
        "recipient": {"peer_id": PEER_A},
        "issued_at": time.time(),
        "outcome": "succeeded",
        "result": {"ok": True},
    }


@pytest.mark.parametrize("malformed", [
    [],
    None,
    "not-an-object",
])
def test_response_validator_rejects_non_object_json(malformed):
    peer_b, client = make_pair()
    request = client.build_request("inventory.get", "1.0", {"item_id": "x"})
    with pytest.raises(OBISRequestError, match="JSON object"):
        validate_response(malformed, request, PEER_A, PEER_B, "succeeded")


def test_response_validator_rejects_extra_peer_reference_fields():
    peer_b, client = make_pair()
    request = client.build_request("inventory.get", "1.0", {"item_id": "x"})
    response = _valid_success_response(request)
    response["sender"]["display_name"] = "untrusted"
    with pytest.raises(OBISRequestError, match="reference"):
        validate_response(response, request, PEER_A, PEER_B, "succeeded")


@pytest.mark.parametrize("timestamp", [-1, float("nan"), float("inf"), 10**10000, True])
def test_response_validator_rejects_invalid_timestamps(timestamp):
    peer_b, client = make_pair()
    request = client.build_request("inventory.get", "1.0", {"item_id": "x"})
    response = _valid_success_response(request)
    response["issued_at"] = timestamp
    with pytest.raises(OBISRequestError, match="timestamp"):
        validate_response(response, request, PEER_A, PEER_B, "succeeded")


def test_response_validator_rejects_malformed_error_envelope():
    peer_b, client = make_pair()
    request = client.build_request("inventory.get", "1.0", {"item_id": "x"})
    response = _valid_success_response(request)
    response.pop("result")
    response["outcome"] = "failed"
    response["error"] = {"code": "authorization.denied"}
    with pytest.raises(OBISRequestError, match="structured error"):
        validate_response(response, request, PEER_A, PEER_B, "failed")


def test_response_validator_rejects_correlation_mismatch():
    peer_b, client = make_pair()
    request = client.build_request("inventory.get", "1.0", {"item_id": "x"})
    response = _valid_success_response(request)
    response["correlation_id"] = "different-request"
    with pytest.raises(OBISRequestError, match="correlation"):
        validate_response(response, request, PEER_A, PEER_B, "succeeded")
