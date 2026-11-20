"""Fail-closed validation for TIIS 0.1 envelopes.

This module validates message shape and binds claimed component identities to
identities supplied by a separately trusted authentication layer. It does not
implement transport, authentication, credential storage, or business execution.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
from importlib.resources import files
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker, ValidationError


class TIISValidationError(ValueError):
    """Raised when an envelope is malformed, stale, or misrouted."""


class TIISAuthorizationError(PermissionError):
    """Raised when sender identity or operation authorization is not approved."""


AuthorizationPolicy = Callable[
    [Mapping[str, Any], Mapping[str, Any], str, str, str], bool
]


def _identity(value: Mapping[str, Any]) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise TIISValidationError("component_identity_invalid")
    keys = ("project_id", "component_id", "instance_id")
    return {key: value[key] for key in keys if key in value}


def _timestamp(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise TIISValidationError(f"{field}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TIISValidationError(f"{field}_timezone_required")
    return parsed.astimezone(timezone.utc)


class TIISValidator:
    """Validate TIIS 0.1 envelopes using caller-supplied trust and policy."""

    def __init__(
        self,
        *,
        authorization_policy: AuthorizationPolicy | None = None,
        max_message_bytes: int = 1_048_576,
        clock_skew_seconds: int = 30,
    ) -> None:
        if not isinstance(max_message_bytes, int) or max_message_bytes < 1:
            raise ValueError("max_message_bytes_must_be_positive")
        if not isinstance(clock_skew_seconds, int) or clock_skew_seconds < 0:
            raise ValueError("clock_skew_seconds_must_be_nonnegative")

        self._authorization_policy = authorization_policy
        self._max_message_bytes = max_message_bytes
        self._clock_skew = timedelta(seconds=clock_skew_seconds)
        schema_path = files("tradix.tiis").joinpath("schemas").joinpath("message.schema.json")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        self._validator = Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        )

    def validate(
        self,
        message: Mapping[str, Any],
        *,
        authenticated_sender: Mapping[str, Any],
        expected_recipient: Mapping[str, Any],
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Validate one message and return a detached dictionary copy.

        authenticated_sender must come from a trusted transport/authentication
        layer or explicitly trusted local adapter. It must never be copied from
        the untrusted message's sender field.
        """
        if not isinstance(message, Mapping):
            raise TIISValidationError("message_must_be_object")

        try:
            detached = dict(message)
            encoded = json.dumps(
                detached,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise TIISValidationError("message_not_json_serializable") from exc

        if len(encoded) > self._max_message_bytes:
            raise TIISValidationError("message_size_limit_exceeded")

        try:
            self._validator.validate(detached)
        except ValidationError as exc:
            raise TIISValidationError("message_schema_invalid") from exc

        if _identity(detached["sender"]) != _identity(authenticated_sender):
            raise TIISAuthorizationError("authenticated_sender_mismatch")
        if _identity(detached["recipient"]) != _identity(expected_recipient):
            raise TIISAuthorizationError("recipient_mismatch")

        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None or current.utcoffset() is None:
            raise ValueError("now_must_be_timezone_aware")
        current = current.astimezone(timezone.utc)
        issued_at = _timestamp(detached["issued_at"], "issued_at")
        if issued_at > current + self._clock_skew:
            raise TIISValidationError("message_issued_in_future")

        expires_at_value = detached.get("expires_at")
        if expires_at_value is not None:
            expires_at = _timestamp(expires_at_value, "expires_at")
            if expires_at <= issued_at:
                raise TIISValidationError("message_expiry_not_after_issue")
            if expires_at <= current:
                raise TIISValidationError("message_expired")

        if self._authorization_policy is None:
            raise TIISAuthorizationError("authorization_policy_not_configured")

        message_type = detached["message_type"]
        action = (
            detached["operation"]
            if message_type == "request"
            else detached["event_type"]
            if message_type == "event"
            else "response"
        )
        allowed = self._authorization_policy(
            _identity(authenticated_sender),
            _identity(expected_recipient),
            detached["interface_id"],
            action,
            message_type,
        )
        if allowed is not True:
            raise TIISAuthorizationError("operation_not_authorized")

        return detached
