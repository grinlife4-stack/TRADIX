"""TIIS envelope adapter for the existing TRADIX factory conversation contract.

The domain InterfaceMessage remains the payload contract. TIIS component identity
is supplied independently and is never inferred from the domain actor role.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import sha256
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from tradix.tiis import TIISAuthorizationError, TIISValidator
from .interface_contract import InterfaceMessage, MessageType, Sender


DOMAIN_CONTRACT_ID = "tradix.factory.interface-message"
DOMAIN_CONTRACT_VERSION = "1.0.0"
TIIS_INTERFACE_ID = "factory.conversation"
TIIS_INTERFACE_VERSION = "1.0.0"

_REQUEST_TYPES = {
    MessageType.USER_INPUT,
    MessageType.MISSION_PROPOSAL,
    MessageType.STATUS_QUERY,
    MessageType.CAPABILITY_QUERY,
    MessageType.CLARIFICATION_ANSWER,
}
_EVENT_TYPES = {
    MessageType.FACTORY_NEED,
    MessageType.STATUS_UPDATE,
    MessageType.RESULT,
    MessageType.BLOCKED,
}


class FactoryTIISAdapterError(ValueError):
    """Raised when a TIIS envelope cannot represent a factory domain message."""


ProjectAuthorization = Callable[[InterfaceMessage], bool]


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _aware_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise FactoryTIISAdapterError("domain_timestamp_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise FactoryTIISAdapterError("domain_timestamp_timezone_required")
    return parsed.astimezone(timezone.utc)


def _component(value: Mapping[str, Any], field: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise FactoryTIISAdapterError(f"{field}_component_identity_invalid")
    allowed = {"project_id", "component_id", "instance_id"}
    if set(value) - allowed or not {"project_id", "component_id"}.issubset(value):
        raise FactoryTIISAdapterError(f"{field}_component_identity_invalid")
    return {key: value[key] for key in ("project_id", "component_id", "instance_id") if key in value}


def _domain_payload(message: InterfaceMessage) -> dict[str, Any]:
    domain = {
        "message_id": message.message_id,
        "conversation_id": message.conversation_id,
        "project_key": message.project_key,
        "correlation_id": message.correlation_id,
        "sender": message.sender.value,
        "message_type": message.message_type.value,
        "body": _plain(message.body),
        "created_at": message.created_at,
    }
    if message.reply_to is not None:
        domain["reply_to"] = message.reply_to
    return domain


def to_tiis_envelope(
    message: InterfaceMessage,
    *,
    sender_component: Mapping[str, Any],
    recipient_component: Mapping[str, Any],
    ttl_seconds: int = 60,
) -> dict[str, Any]:
    """Wrap an existing domain message in a TIIS 0.1 component envelope.

    This function only maps data. It does not authenticate, authorize, send, or
    persist the message. The caller must supply the real component identities.
    """
    if not isinstance(message, InterfaceMessage):
        raise TypeError("message_must_be_InterfaceMessage")
    if not isinstance(ttl_seconds, int) or not 1 <= ttl_seconds <= 3600:
        raise ValueError("ttl_seconds_must_be_between_1_and_3600")

    sender = _component(sender_component, "sender")
    recipient = _component(recipient_component, "recipient")
    issued = _aware_timestamp(message.created_at)
    domain_message = _domain_payload(message)
    stable_scope = f"{message.project_key}:{message.message_id}"
    stable_correlation = f"{message.project_key}:{message.correlation_id}"

    envelope: dict[str, Any] = {
        "protocol": "TIIS",
        "protocol_version": "0.1",
        "message_type": "request" if message.message_type in _REQUEST_TYPES else "event",
        "message_id": str(uuid5(NAMESPACE_URL, f"tradix:tiis:message:{stable_scope}")),
        "correlation_id": str(uuid5(NAMESPACE_URL, f"tradix:tiis:correlation:{stable_correlation}")),
        "sender": sender,
        "recipient": recipient,
        "interface_id": TIIS_INTERFACE_ID,
        "interface_version": TIIS_INTERFACE_VERSION,
        "issued_at": issued.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "payload": {
            "contract_id": DOMAIN_CONTRACT_ID,
            "contract_version": DOMAIN_CONTRACT_VERSION,
            "message": domain_message,
        },
    }

    if message.message_type in _REQUEST_TYPES:
        envelope["operation"] = message.message_type.value.replace("_", "-")
        envelope["expires_at"] = (
            issued + timedelta(seconds=ttl_seconds)
        ).isoformat(timespec="seconds").replace("+00:00", "Z")
        digest = sha256(f"{stable_scope}".encode("utf-8")).hexdigest()
        envelope["idempotency_key"] = f"tiis-{digest}"
    elif message.message_type in _EVENT_TYPES:
        envelope["event_type"] = f"factory.{message.message_type.value.replace('_', '-')}"
    else:
        raise FactoryTIISAdapterError("unsupported_factory_message_type")

    return envelope


def from_tiis_envelope(
    envelope: Mapping[str, Any],
    *,
    validator: TIISValidator,
    authenticated_sender: Mapping[str, Any],
    expected_recipient: Mapping[str, Any],
    project_authorizer: ProjectAuthorization | None,
    now: datetime | None = None,
) -> InterfaceMessage:
    """Validate the TIIS envelope and reconstruct its domain InterfaceMessage.

    Component authorization is performed by TIISValidator. Product/project
    authorization is a separate mandatory check because the factory component
    may serve multiple independently owned products.
    """
    if project_authorizer is None:
        raise TIISAuthorizationError("factory_project_policy_not_configured")

    checked = validator.validate(
        envelope,
        authenticated_sender=authenticated_sender,
        expected_recipient=expected_recipient,
        now=now,
    )
    if checked["interface_id"] != TIIS_INTERFACE_ID:
        raise FactoryTIISAdapterError("unexpected_factory_interface")
    if checked["interface_version"] != TIIS_INTERFACE_VERSION:
        raise FactoryTIISAdapterError("unsupported_factory_interface_version")

    payload = checked.get("payload")
    if not isinstance(payload, Mapping) or set(payload) != {
        "contract_id",
        "contract_version",
        "message",
    }:
        raise FactoryTIISAdapterError("factory_domain_payload_invalid")
    if payload["contract_id"] != DOMAIN_CONTRACT_ID:
        raise FactoryTIISAdapterError("factory_domain_contract_mismatch")
    if payload["contract_version"] != DOMAIN_CONTRACT_VERSION:
        raise FactoryTIISAdapterError("unsupported_factory_domain_contract")

    domain = payload["message"]
    required = {
        "message_id",
        "conversation_id",
        "project_key",
        "correlation_id",
        "sender",
        "message_type",
        "body",
        "created_at",
    }
    optional = {"reply_to"}
    if not isinstance(domain, Mapping):
        raise FactoryTIISAdapterError("factory_domain_message_invalid")
    if required - set(domain) or set(domain) - required - optional:
        raise FactoryTIISAdapterError("factory_domain_message_fields_invalid")

    try:
        sender = Sender(domain["sender"])
        message_type = MessageType(domain["message_type"])
        result = InterfaceMessage(
            message_id=domain["message_id"],
            conversation_id=domain["conversation_id"],
            project_key=domain["project_key"],
            correlation_id=domain["correlation_id"],
            sender=sender,
            message_type=message_type,
            body=domain["body"],
            created_at=domain["created_at"],
            reply_to=domain.get("reply_to"),
        )
    except (TypeError, ValueError) as exc:
        raise FactoryTIISAdapterError("factory_domain_message_rejected") from exc

    expected_outer_type = "request" if result.message_type in _REQUEST_TYPES else "event"
    if checked["message_type"] != expected_outer_type:
        raise FactoryTIISAdapterError("domain_and_tiis_message_types_disagree")
    if expected_outer_type == "request":
        if checked.get("operation") != result.message_type.value.replace("_", "-"):
            raise FactoryTIISAdapterError("domain_and_tiis_operation_disagree")
    elif checked.get("event_type") != f"factory.{result.message_type.value.replace('_', '-')}":
        raise FactoryTIISAdapterError("domain_and_tiis_event_type_disagree")

    if project_authorizer(result) is not True:
        raise TIISAuthorizationError("factory_project_scope_not_authorized")
    return result
