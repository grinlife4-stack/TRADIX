from datetime import datetime, timezone
from pathlib import Path

import pytest

from tradix.tiis import TIISAuthorizationError, TIISValidationError, TIISValidator


CANONICAL_SCHEMA = Path(__file__).parents[1] / "standards" / "tiis" / "0.1" / "message.schema.json"
PACKAGED_SCHEMA = (
    Path(__file__).parents[1]
    / "src"
    / "tradix"
    / "tiis"
    / "schemas"
    / "message.schema.json"
)
NOW = datetime(2026, 11, 20, 10, 0, 10, tzinfo=timezone.utc)
SENDER = {"project_id": "tradix", "component_id": "artifact-gateway"}
RECIPIENT = {"project_id": "tradix", "component_id": "tool-catalog"}


def request_message() -> dict:
    return {
        "protocol": "TIIS",
        "protocol_version": "0.1",
        "message_type": "request",
        "message_id": "11111111-1111-4111-8111-111111111111",
        "correlation_id": "22222222-2222-4222-8222-222222222222",
        "sender": dict(SENDER),
        "recipient": dict(RECIPIENT),
        "interface_id": "artifact.receipt.read",
        "interface_version": "0.1.0",
        "operation": "get-receipt",
        "issued_at": "2026-11-20T10:00:00Z",
        "expires_at": "2026-11-20T10:00:30Z",
        "payload": {"receipt_id": "receipt-001"},
    }


def allow_all_for_test(*_args) -> bool:
    return True


def test_packaged_schema_is_byte_identical_to_canonical_schema() -> None:
    assert PACKAGED_SCHEMA.read_bytes() == CANONICAL_SCHEMA.read_bytes()


def test_validator_accepts_valid_request_with_authenticated_sender_and_policy() -> None:
    validator = TIISValidator(authorization_policy=allow_all_for_test)
    result = validator.validate(
        request_message(),
        authenticated_sender=SENDER,
        expected_recipient=RECIPIENT,
        now=NOW,
    )
    assert result["operation"] == "get-receipt"


def test_validator_fails_closed_without_authorization_policy() -> None:
    validator = TIISValidator()
    with pytest.raises(TIISAuthorizationError, match="authorization_policy_not_configured"):
        validator.validate(
            request_message(),
            authenticated_sender=SENDER,
            expected_recipient=RECIPIENT,
            now=NOW,
        )


def test_claimed_sender_must_match_authenticated_transport_identity() -> None:
    validator = TIISValidator(authorization_policy=allow_all_for_test)
    with pytest.raises(TIISAuthorizationError, match="authenticated_sender_mismatch"):
        validator.validate(
            request_message(),
            authenticated_sender={"project_id": "tradix", "component_id": "untrusted-peer"},
            expected_recipient=RECIPIENT,
            now=NOW,
        )


def test_recipient_must_match_local_component_identity() -> None:
    validator = TIISValidator(authorization_policy=allow_all_for_test)
    with pytest.raises(TIISAuthorizationError, match="recipient_mismatch"):
        validator.validate(
            request_message(),
            authenticated_sender=SENDER,
            expected_recipient={"project_id": "tradix", "component_id": "other-service"},
            now=NOW,
        )


def test_expired_and_future_messages_are_rejected() -> None:
    validator = TIISValidator(authorization_policy=allow_all_for_test)
    expired = request_message()
    expired["expires_at"] = "2026-11-20T10:00:09Z"
    with pytest.raises(TIISValidationError, match="message_expired"):
        validator.validate(expired, authenticated_sender=SENDER, expected_recipient=RECIPIENT, now=NOW)

    future = request_message()
    future["issued_at"] = "2026-11-20T10:01:00Z"
    with pytest.raises(TIISValidationError, match="message_issued_in_future"):
        validator.validate(future, authenticated_sender=SENDER, expected_recipient=RECIPIENT, now=NOW)


def test_message_size_is_bounded_before_policy_execution() -> None:
    called = False

    def policy(*_args):
        nonlocal called
        called = True
        return True

    validator = TIISValidator(authorization_policy=policy, max_message_bytes=256)
    message = request_message()
    message["payload"] = {"data": "x" * 1000}
    with pytest.raises(TIISValidationError, match="message_size_limit_exceeded"):
        validator.validate(message, authenticated_sender=SENDER, expected_recipient=RECIPIENT, now=NOW)
    assert called is False


def test_policy_denial_is_fail_closed() -> None:
    validator = TIISValidator(authorization_policy=lambda *_args: False)
    with pytest.raises(TIISAuthorizationError, match="operation_not_authorized"):
        validator.validate(
            request_message(),
            authenticated_sender=SENDER,
            expected_recipient=RECIPIENT,
            now=NOW,
        )


def test_invalid_envelope_is_rejected_before_authorization() -> None:
    called = False

    def policy(*_args):
        nonlocal called
        called = True
        return True

    validator = TIISValidator(authorization_policy=policy)
    message = request_message()
    message["api_key"] = "must-not-be-carried"
    with pytest.raises(TIISValidationError, match="message_schema_invalid"):
        validator.validate(message, authenticated_sender=SENDER, expected_recipient=RECIPIENT, now=NOW)
    assert called is False
