import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError


SCHEMA_PATH = Path(__file__).parents[1] / "standards" / "tiis" / "0.1" / "message.schema.json"
FORMAT_CHECKER = FormatChecker()


def load_validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FORMAT_CHECKER)


def request_message() -> dict:
    return {
        "protocol": "TIIS",
        "protocol_version": "0.1",
        "message_type": "request",
        "message_id": "11111111-1111-4111-8111-111111111111",
        "correlation_id": "22222222-2222-4222-8222-222222222222",
        "sender": {"project_id": "tradix", "component_id": "artifact-gateway"},
        "recipient": {"project_id": "tradix", "component_id": "tool-catalog"},
        "interface_id": "artifact.receipt.read",
        "interface_version": "0.1.0",
        "operation": "get-receipt",
        "issued_at": "2026-11-20T10:00:00Z",
        "expires_at": "2026-11-20T10:00:30Z",
        "payload": {"receipt_id": "receipt-001"},
    }


def test_tiis_schema_is_valid_draft_2020_12() -> None:
    load_validator()


def test_valid_request_envelope_is_accepted() -> None:
    load_validator().validate(request_message())


def test_valid_success_response_is_accepted() -> None:
    request = request_message()
    response = {
        "protocol": "TIIS",
        "protocol_version": "0.1",
        "message_type": "response",
        "message_id": "33333333-3333-4333-8333-333333333333",
        "correlation_id": request["correlation_id"],
        "in_reply_to": request["message_id"],
        "sender": request["recipient"],
        "recipient": request["sender"],
        "interface_id": request["interface_id"],
        "interface_version": request["interface_version"],
        "issued_at": "2026-11-20T10:00:01Z",
        "outcome": "succeeded",
        "payload": {"found": True},
    }
    load_validator().validate(response)


def test_failed_response_requires_normalized_error() -> None:
    request = request_message()
    response = {
        "protocol": "TIIS",
        "protocol_version": "0.1",
        "message_type": "response",
        "message_id": "33333333-3333-4333-8333-333333333333",
        "correlation_id": request["correlation_id"],
        "in_reply_to": request["message_id"],
        "sender": request["recipient"],
        "recipient": request["sender"],
        "interface_id": request["interface_id"],
        "interface_version": request["interface_version"],
        "issued_at": "2026-11-20T10:00:01Z",
        "outcome": "failed",
        "payload": {},
    }
    with pytest.raises(ValidationError):
        load_validator().validate(response)
    response["error"] = {"code": "dependency.timeout", "message": "The dependency timed out.", "retryable": True}
    load_validator().validate(response)


def test_event_envelope_is_accepted() -> None:
    event = {
        "protocol": "TIIS",
        "protocol_version": "0.1",
        "message_type": "event",
        "message_id": "44444444-4444-4444-8444-444444444444",
        "sender": {"project_id": "tradix", "component_id": "tool-catalog"},
        "recipient": {"project_id": "tradix", "component_id": "factory-ledger"},
        "interface_id": "catalog.lifecycle",
        "interface_version": "0.1.0",
        "event_type": "tool.lifecycle.changed",
        "issued_at": "2026-11-20T10:00:00Z",
        "payload": {"tool_id": "example-tool", "state": "approved"},
    }
    load_validator().validate(event)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda message: message.update(protocol="OBIS"),
        lambda message: message.update(protocol_version="1.0"),
        lambda message: message.update(message_type="command"),
        lambda message: message.update(interface_version="v0"),
        lambda message: message.update(sender={"project_id": "tradix"}),
        lambda message: message.update(expires_at="not-a-date"),
        lambda message: message.update(api_key="must-not-be-carried-in-message"),
        lambda message: message.update(secret="must-not-be-carried-in-message"),
    ],
)
def test_invalid_or_unsafe_envelopes_are_rejected(mutation) -> None:
    message = request_message()
    mutation(message)
    with pytest.raises(ValidationError):
        load_validator().validate(message)


def test_request_requires_expiry_and_typed_payload() -> None:
    message = request_message()
    del message["expires_at"]
    with pytest.raises(ValidationError):
        load_validator().validate(message)
    message = request_message()
    message["payload"] = "untyped"
    with pytest.raises(ValidationError):
        load_validator().validate(message)


def test_request_idempotency_key_is_bounded_when_present() -> None:
    message = request_message()
    message["idempotency_key"] = "k" * 16
    load_validator().validate(message)
    message["idempotency_key"] = "short"
    with pytest.raises(ValidationError):
        load_validator().validate(message)
