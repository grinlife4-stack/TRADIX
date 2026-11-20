"""TIIS 0.1 interface adapter for the metadata-only Tool Catalog.

The adapter calls the catalog's public methods. It does not expose SQLite,
accept caller-supplied actor identities, or grant execution authority.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from tradix.tiis import TIISValidator
from .catalog import ToolCatalog, ToolDescriptor, ToolStatusError


INTERFACE_ID = "tool.catalog"
INTERFACE_VERSION = "0.1.0"


class CatalogTIISAdapterError(ValueError):
    """Raised when a TIIS request is not a valid catalog operation."""


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _fields(payload: Mapping[str, Any], required: set[str], optional: set[str] = frozenset()) -> None:
    if not isinstance(payload, Mapping):
        raise CatalogTIISAdapterError("payload_must_be_object")
    missing = required - set(payload)
    unknown = set(payload) - required - optional
    if missing or unknown:
        raise CatalogTIISAdapterError("payload_fields_invalid")


def _tuple_values(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or len(value) > 64:
        raise CatalogTIISAdapterError(f"{field}_must_be_bounded_array")
    if any(not isinstance(item, str) for item in value):
        raise CatalogTIISAdapterError(f"{field}_entries_must_be_strings")
    return tuple(value)


def _actor(identity: Mapping[str, Any]) -> str:
    project = identity.get("project_id")
    component = identity.get("component_id")
    instance = identity.get("instance_id")
    value = f"{project}/{component}" + (f"/{instance}" if instance else "")
    if not isinstance(project, str) or not isinstance(component, str):
        raise CatalogTIISAdapterError("authenticated_actor_invalid")
    return value


def _timestamp(now: datetime | None) -> str:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now_must_be_timezone_aware")
    return current.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class ToolCatalogTIISAdapter:
    """Expose narrow catalog operations through authenticated TIIS envelopes."""

    def __init__(
        self,
        catalog: ToolCatalog,
        validator: TIISValidator,
        component_identity: Mapping[str, Any],
    ) -> None:
        if not isinstance(catalog, ToolCatalog):
            raise TypeError("catalog_must_be_ToolCatalog")
        self._catalog = catalog
        self._validator = validator
        self._identity = dict(component_identity)

    def handle(
        self,
        message: Mapping[str, Any],
        *,
        authenticated_sender: Mapping[str, Any],
        now: datetime | None = None,
    ) -> dict[str, Any]:
        checked = self._validator.validate(
            message,
            authenticated_sender=authenticated_sender,
            expected_recipient=self._identity,
            now=now,
        )
        if checked["message_type"] != "request":
            raise CatalogTIISAdapterError("catalog_accepts_requests_only")
        if checked["interface_id"] != INTERFACE_ID:
            raise CatalogTIISAdapterError("unexpected_interface")
        if checked["interface_version"] != INTERFACE_VERSION:
            raise CatalogTIISAdapterError("unsupported_interface_version")

        operation = checked["operation"]
        payload = checked["payload"]
        actor = _actor(authenticated_sender)

        try:
            result = self._dispatch(operation, payload, actor)
        except CatalogTIISAdapterError:
            return self._response(
                checked,
                outcome="rejected",
                payload={},
                error={
                    "code": "catalog.request-invalid",
                    "message": "The catalog request does not match the declared operation contract.",
                    "retryable": False,
                },
                now=now,
            )
        except KeyError:
            return self._response(
                checked,
                outcome="failed",
                payload={},
                error={
                    "code": "catalog.not-found",
                    "message": "The requested catalog record does not exist.",
                    "retryable": False,
                },
                now=now,
            )
        except (ToolStatusError, ValueError, TypeError):
            return self._response(
                checked,
                outcome="rejected",
                payload={},
                error={
                    "code": "catalog.operation-rejected",
                    "message": "The catalog rejected the requested operation.",
                    "retryable": False,
                },
                now=now,
            )

        return self._response(
            checked,
            outcome="succeeded",
            payload={"result": _plain(result)},
            now=now,
        )

    def _dispatch(self, operation: str, payload: Mapping[str, Any], actor: str) -> Any:
        if operation == "get":
            _fields(payload, {"tool_id", "version"})
            return self._catalog.get(payload["tool_id"], payload["version"])

        if operation == "list":
            _fields(payload, set(), {"status", "category"})
            return self._catalog.list_tools(
                status=payload.get("status"),
                category=payload.get("category"),
            )

        if operation == "history":
            _fields(payload, {"tool_id", "version"})
            return self._catalog.history(payload["tool_id"], payload["version"])

        if operation == "register":
            _fields(payload, {"descriptor"}, {"reason"})
            descriptor_data = payload["descriptor"]
            descriptor_required = {
                "tool_id", "version", "category", "source_uri", "license_id",
                "platforms", "capabilities", "execution_modes",
                "adapter_contract_version", "free_open_source",
            }
            _fields(descriptor_data, descriptor_required, {"notes"})
            descriptor = ToolDescriptor(
                tool_id=descriptor_data["tool_id"],
                version=descriptor_data["version"],
                category=descriptor_data["category"],
                source_uri=descriptor_data["source_uri"],
                license_id=descriptor_data["license_id"],
                platforms=_tuple_values(descriptor_data["platforms"], "platforms"),
                capabilities=_tuple_values(descriptor_data["capabilities"], "capabilities"),
                execution_modes=_tuple_values(descriptor_data["execution_modes"], "execution_modes"),
                adapter_contract_version=descriptor_data["adapter_contract_version"],
                free_open_source=descriptor_data["free_open_source"],
                notes=descriptor_data.get("notes", ""),
            )
            self._catalog.register(
                descriptor,
                actor=actor,
                reason=payload.get("reason", "registered through TIIS"),
            )
            return {"tool_id": descriptor.tool_id, "version": descriptor.version, "status": "discovered"}

        if operation == "transition":
            _fields(
                payload,
                {"tool_id", "version", "status", "reason"},
                {"evidence_ref"},
            )
            self._catalog.transition(
                tool_id=payload["tool_id"],
                version=payload["version"],
                status=payload["status"],
                actor=actor,
                reason=payload["reason"],
                evidence_ref=payload.get("evidence_ref", ""),
            )
            return {
                "tool_id": payload["tool_id"],
                "version": payload["version"],
                "status": payload["status"],
            }

        raise CatalogTIISAdapterError("unsupported_operation")

    def _response(
        self,
        request: Mapping[str, Any],
        *,
        outcome: str,
        payload: Mapping[str, Any],
        error: Mapping[str, Any] | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        response = {
            "protocol": "TIIS",
            "protocol_version": "0.1",
            "message_type": "response",
            "message_id": str(uuid4()),
            "correlation_id": request["correlation_id"],
            "in_reply_to": request["message_id"],
            "sender": self._identity,
            "recipient": request["sender"],
            "interface_id": INTERFACE_ID,
            "interface_version": INTERFACE_VERSION,
            "issued_at": _timestamp(now),
            "outcome": outcome,
            "payload": dict(payload),
        }
        if error is not None:
            response["error"] = dict(error)
        return response
