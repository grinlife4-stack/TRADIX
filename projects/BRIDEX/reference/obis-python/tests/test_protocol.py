from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

import pytest

from obis_bridge import Credential, OBISClient, OBISPeer, OBISRequestError, OBISServer, SQLiteReplayGuard, register_ecoscan_inventory_capability
from obis_bridge.peer import MAX_MESSAGE_BYTES, MAX_TTL_SECONDS, MESSAGE_PATH, ReplayGuard, canonical_json, sign_message, strict_json_loads, validate_request, validate_response, verify_signature


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
    request = client.build_request("inventory.get", "1.0", {"item_id": "x"})
    request["authorization"]["scopes"] = ["profile:read"]
    with pytest.raises(OBISRequestError, match="required scope"):
        peer_b.handle(request, KEY_ID, sign_message(request, SECRET))


def test_capability_cannot_be_invoked_with_ungranted_scope():
    peer_b, client = make_pair()
    request = client.build_request("inventory.get", "1.0", {"item_id": "x"})
    request["authorization"]["scopes"].append("admin:all")
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
    request_message = client.build_request("inventory.get", "1.0", {"item_id": "sku-42"})
    request_message["authorization"]["scopes"] = ["profile:read"]
    body = canonical_json(request_message)
    signature = sign_message(request_message, SECRET)
    with OBISServer(peer_b) as server:
        request = urllib.request.Request(
            server.address + MESSAGE_PATH,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/obis+json",
                "X-OBIS-Key-Id": KEY_ID,
                "X-OBIS-Signature": signature,
            },
        )
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(request, timeout=2)
        error_body = exc.value.read(MAX_MESSAGE_BYTES + 1)
        response_signature = exc.value.headers.get("X-OBIS-Signature", "")
    error_message = strict_json_loads(error_body.decode("utf-8"))
    assert verify_signature(error_message, SECRET, response_signature)
    validate_response(error_message, request_message, PEER_A, PEER_B, "failed")
    assert error_message["error"]["code"] == "authorization.denied"
    assert "required scope" in error_message["error"]["message"]


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


@pytest.mark.parametrize("timestamp", [-1, float("nan"), float("inf"), 10**400, True])
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


def test_client_cannot_request_scopes_outside_its_local_grant():
    peer_b, client = make_pair()
    with pytest.raises(ValueError, match="local client grant"):
        client.build_request("inventory.get", "1.0", {"item_id": "x"}, scopes={"admin:all"})


def test_capability_result_must_be_json_serializable():
    credential = Credential(KEY_ID, PEER_A, PRINCIPAL_A, SECRET, frozenset({"inventory:read"}))
    peer = OBISPeer(PEER_B, [credential])
    peer.register_capability("inventory.get", "1.0", {"inventory:read"}, lambda _: {"bad": {1, 2}})
    _, client = make_pair()
    request = client.build_request("inventory.get", "1.0", {"item_id": "x"})
    with pytest.raises(OBISRequestError) as exc:
        peer.handle(request, KEY_ID, sign_message(request, SECRET))
    assert exc.value.code == "operation.invalid_result"


def test_capability_result_size_is_bounded():
    credential = Credential(KEY_ID, PEER_A, PRINCIPAL_A, SECRET, frozenset({"inventory:read"}))
    peer = OBISPeer(PEER_B, [credential])
    peer.register_capability(
        "inventory.get", "1.0", {"inventory:read"},
        lambda _: {"data": "x" * (MAX_MESSAGE_BYTES + 100)},
    )
    _, client = make_pair()
    request = client.build_request("inventory.get", "1.0", {"item_id": "x"})
    with pytest.raises(OBISRequestError) as exc:
        peer.handle(request, KEY_ID, sign_message(request, SECRET))
    assert exc.value.code == "operation.result_too_large"


def test_client_rejects_non_bare_loopback_urls():
    peer_b, client = make_pair()
    for endpoint in (
        "http://user:pass@127.0.0.1:8080",
        "http://127.0.0.1:8080/path",
        "http://127.0.0.1:8080/?token=x",
        "http://127.0.0.1:8080/#fragment",
    ):
        with pytest.raises(ValueError, match="endpoint"):
            client.invoke(endpoint, "inventory.get", "1.0", {"item_id": "x"})


def test_client_timeout_must_be_finite_and_positive():
    with pytest.raises(ValueError, match="timeout"):
        OBISClient(PEER_A, PEER_B, KEY_ID, PRINCIPAL_A, SECRET, {"inventory:read"}, timeout=0)



def make_ecoscan_inventory_pair():
    credential = Credential(
        key_id=KEY_ID,
        peer_id=PEER_A,
        principal_ref=PRINCIPAL_A,
        secret=SECRET,
        allowed_scopes=frozenset({"ecoscan:inventory:read"}),
        allowed_resources=frozenset({("project-a", "source-a")}),
    )
    peer = OBISPeer(PEER_B, [credential])
    provider_calls = []

    def provider(project_id, source_id, kinds):
        provider_calls.append((project_id, source_id, kinds))
        return {
            "coverage_state": "COMPLETE",
            "items_seen": 3,
            "pages_seen": 1,
            "measurements": {"logical_bytes": 8192, "file_count": 3},
            "source_timestamp": "2026-11-20T10:00:00Z",
            "limitations": [],
            "evidence_ref": "inventory-evidence-01",
        }

    register_ecoscan_inventory_capability(peer, provider)
    client = OBISClient(
        local_peer_id=PEER_A,
        remote_peer_id=PEER_B,
        key_id=KEY_ID,
        principal_ref=PRINCIPAL_A,
        secret=SECRET,
        scopes={"ecoscan:inventory:read"},
    )
    return peer, client, provider_calls


def test_ecoscan_inventory_capability_works_over_real_loopback_obis_http():
    peer, client, provider_calls = make_ecoscan_inventory_pair()
    with OBISServer(peer) as server:
        response = client.invoke(
            server.address,
            "ecoscan.inventory.read",
            "1.0",
            {
                "project_id": "project-a",
                "source_id": "source-a",
                "measurement_kinds": ["logical_bytes", "file_count"],
            },
        )
    assert response["outcome"] == "succeeded"
    assert response["result"]["project_id"] == "project-a"
    assert response["result"]["source_id"] == "source-a"
    assert response["result"]["measurements"] == {"logical_bytes": 8192, "file_count": 3}
    assert provider_calls == [("project-a", "source-a", ("logical_bytes", "file_count"))]


def test_ecoscan_inventory_capability_denies_ungranted_project_source_before_provider_call():
    peer, client, provider_calls = make_ecoscan_inventory_pair()
    with OBISServer(peer) as server:
        with pytest.raises(OBISRequestError, match="outside credential resource grant"):
            client.invoke(
                server.address,
                "ecoscan.inventory.read",
                "1.0",
                {
                    "project_id": "project-b",
                    "source_id": "source-b",
                    "measurement_kinds": ["logical_bytes", "file_count"],
                },
            )
    assert provider_calls == []


def test_ecoscan_inventory_capability_rejects_unsupported_measurement_kind():
    peer, client, provider_calls = make_ecoscan_inventory_pair()
    with OBISServer(peer) as server:
        with pytest.raises(OBISRequestError):
            client.invoke(
                server.address,
                "ecoscan.inventory.read",
                "1.0",
                {
                    "project_id": "project-a",
                    "source_id": "source-a",
                    "measurement_kinds": ["admin_dump"],
                },
            )
    assert provider_calls == []


def test_documented_obis_request_example_validates_against_canonical_schema():
    """Keep the normative Section 9 request example aligned with the 0.1 wire schema."""
    import re
    from pathlib import Path
    from jsonschema import Draft202012Validator

    repo_root = Path(__file__).resolve().parents[5]
    specification = (repo_root / "docs" / "OBIS_SPECIFICATION.md").read_text(encoding="utf-8")
    section = specification.split("## 9. Message envelope", 1)[1].split("\n## ", 1)[0]
    match = re.search(r"```json\s*(\{.*?\})\s*```", section, re.DOTALL)
    assert match is not None, "Section 9 must contain a JSON request example"
    example = json.loads(match.group(1))

    canonical_schema = json.loads(
        (repo_root / "standards" / "obis" / "0.1" / "message.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(canonical_schema).validate(example)


def test_sqlite_replay_guard_rejects_nonce_after_peer_restart(tmp_path):
    database = tmp_path / "replay.sqlite3"
    first_process_guard = SQLiteReplayGuard(database)
    assert first_process_guard.accept("key-1:nonce-1", now=1000)
    del first_process_guard

    restarted_process_guard = SQLiteReplayGuard(database)
    assert not restarted_process_guard.accept("key-1:nonce-1", now=1001)
    assert restarted_process_guard.accept("key-1:nonce-2", now=1001)


def test_sqlite_replay_guard_expires_old_nonce_records(tmp_path):
    guard = SQLiteReplayGuard(tmp_path / "replay.sqlite3", retention_seconds=10)
    assert guard.accept("key-1:nonce-1", now=1000)
    assert guard.accept("key-1:nonce-1", now=1010)


def test_sqlite_replay_guard_rejects_memory_database():
    with pytest.raises(ValueError, match="filesystem database path"):
        SQLiteReplayGuard(":memory:")


def test_replay_storage_failure_fails_closed_before_capability_execution():
    executed = []
    credential = Credential(
        key_id=KEY_ID,
        peer_id=PEER_A,
        principal_ref=PRINCIPAL_A,
        secret=SECRET,
        allowed_scopes=frozenset({"inventory:read"}),
    )
    peer = OBISPeer(PEER_B, [credential])
    peer.register_capability(
        "inventory.get", "1.0", {"inventory:read"},
        lambda payload: executed.append(payload) or {"ok": True},
    )

    class BrokenReplayGuard:
        def accept(self, nonce, now=None):
            raise OSError("storage unavailable")

    peer.replay_guard = BrokenReplayGuard()
    client = OBISClient(PEER_A, PEER_B, KEY_ID, PRINCIPAL_A, SECRET, {"inventory:read"})
    request = client.build_request("inventory.get", "1.0", {"item_id": "sku-42"})
    with pytest.raises(OBISRequestError) as exc:
        peer.handle(request, KEY_ID, sign_message(request, SECRET))

    assert exc.value.code == "replay.storage_unavailable"
    assert exc.value.http_status == 503
    assert executed == []



def test_obis_02_operation_schema_is_valid_and_packaged_copies_match():
    from importlib.resources import files
    from jsonschema import Draft202012Validator

    canonical_path = Path(__file__).resolve().parents[5] / "standards" / "obis" / "0.2" / "message.schema.json"
    canonical_bytes = canonical_path.read_bytes()
    package_root = files("obis_bridge").joinpath("schemas")
    packaged_bytes = package_root.joinpath("obis-0.2-message.schema.json").read_bytes()
    source_copy = package_root.joinpath("message-0.2.schema.json").read_bytes()
    assert canonical_bytes == packaged_bytes == source_copy
    schema = json.loads(canonical_bytes)
    Draft202012Validator.check_schema(schema)


def test_obis_02_schema_accepts_operation_request_status_and_unknown_response():
    from importlib.resources import files
    from jsonschema import Draft202012Validator

    schema_path = files("obis_bridge").joinpath("schemas/obis-0.2-message.schema.json")
    validator = Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8")))
    common = {
        "protocol": "obis",
        "version": "0.2",
        "message_id": "message-1",
        "nonce": "nonce-1",
        "attempt_id": "attempt-1",
        "sender": {"peer_id": "peer:caller"},
        "recipient": {"peer_id": "peer:owner"},
        "issued_at": 1795168810,
        "expires_at": 1795168840,
        "capability": {"id": "records.write", "version": "1.0"},
        "authorization": {"principal_ref": "principal:caller", "scopes": ["records:write"]},
    }
    operation_request = {
        **common,
        "message_type": "request",
        "operation": {
            "operation_id": "operation-42",
            "idempotency_key": "idem-42",
            "request_hash": "a" * 64,
            "expires_at": 1795169810,
        },
        "payload": {"record_id": "record-42"},
    }
    status_request = {
        **common,
        "message_type": "operation_status_request",
        "operation_id": "operation-42",
    }
    operation_response = {
        "protocol": "obis",
        "version": "0.2",
        "message_type": "operation_response",
        "message_id": "response-1",
        "correlation_id": "message-1",
        "sender": {"peer_id": "peer:owner"},
        "recipient": {"peer_id": "peer:caller"},
        "issued_at": 1795168811,
        "operation": {
            "operation_id": "operation-42",
            "request_hash": "a" * 64,
            "state": "UNKNOWN",
            "result": None,
            "result_ref": None,
            "failure_code": None,
            "created_at": 1795168810,
            "updated_at": 1795168811,
            "expires_at": 1795169810,
        },
    }
    for message in (operation_request, status_request, operation_response):
        validator.validate(message)


def test_obis_02_schema_rejects_invalid_request_hash():
    from importlib.resources import files
    from jsonschema import Draft202012Validator, ValidationError

    schema_path = files("obis_bridge").joinpath("schemas/obis-0.2-message.schema.json")
    validator = Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8")))
    invalid = {
        "protocol": "obis",
        "version": "0.2",
        "message_type": "request",
        "message_id": "message-1",
        "nonce": "nonce-1",
        "attempt_id": "attempt-1",
        "sender": {"peer_id": "peer:caller"},
        "recipient": {"peer_id": "peer:owner"},
        "issued_at": 1795168810,
        "expires_at": 1795168840,
        "capability": {"id": "records.write", "version": "1.0"},
        "authorization": {"principal_ref": "principal:caller", "scopes": ["records:write"]},
        "operation": {
            "operation_id": "operation-42",
            "idempotency_key": "idem-42",
            "request_hash": "not-a-sha256",
            "expires_at": 1795169810,
        },
        "payload": {"record_id": "record-42"},
    }
    with pytest.raises(ValidationError):
        validator.validate(invalid)
