"""Fail-closed TIIS adapter for the TRADIX metadata-only Tool Catalog.

Only read operations are exposed. The adapter does not add a network listener,
authenticate credentials, mutate catalog lifecycle state, or execute tools.
The caller must supply an authenticated principal from a trusted local boundary.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from tradix.tiis import TIISAuthorizationError, TIISValidationError, TIISValidator
from .catalog import ToolCatalog


INTERFACE_ID = "tool.catalog"
INTERFACE_VERSION = "1.0.0"
_ALLOWED_OPERATIONS = {"tool.get", "tool.list"}


class ToolCatalogTIISAdapter:
    """Expose bounded, read-only Tool Catalog queries through TIIS 0.1."""

    def __init__(
        self,
        catalog: ToolCatalog,
        validator: TIISValidator,
        local_component: Mapping[str, str],
    ) -> None:
        if not isinstance(catalog, ToolCatalog):
            raise TypeError("catalog_must_be_ToolCatalog")
        if not isinstance(validator, TIISValidator):
            raise TypeError("validator_must_be_TIISValidator")
        self._catalog = catalog
        self._validator = validator
        self._local_component = self._component(local_component)

    @staticmethod
    def _component(value: Mapping[str, str]) -> dict[str, str]:
        if not isinstance(value, Mapping):
            raise TIISValidationError("component_identity_invalid")
        allowed = {"project_id", "component_id", "instance_id"}
        required = {"project_id", "component_id"}
        if set(value) - allowed or not required.issubset(value):
            raise TIISValidationError("component_identity_invalid")
        if any(not isinstance(value[key], str) or not value[key] for key in required):
            raise TIISValidationError("component_identity_invalid")
        if "instance_id" in value and (
            not isinstance(value["instance_id"], str) or not value["instance_id"]
        ):
            raise TIISValidationError("component_identity_invalid")
        return {key: value[key] for key in ("project_id", "component_id", "instance_id") if key in value}

    @staticmethod
    def _jsonable(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {str(key): ToolCatalogTIISAdapter._jsonable(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return [ToolCatalogTIISAdapter._jsonable(item) for item in value]
        return value

    @staticmethod
    def _issued_at(now: datetime | None) -> str:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None or current.utcoffset() is None:
            raise ValueError("now_must_be_timezone_aware")
        return current.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    def handle(
        self,
        request: Mapping[str, Any],
        *,
        authenticated_sender: Mapping[str, str],
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Validate and handle one TIIS request from a trusted local caller.

        authenticated_sender MUST be obtained from the caller's trusted
        authentication context, never copied from request['sender'].
        """
        sender = self._component(authenticated_sender)
        checked = self._validator.validate(
            request,
            authenticated_sender=sender,
            expected_recipient=self._local_component,
            now=now,
        )
        if checked["message_type"] != "request":
            raise TIISValidationError("tool_catalog_accepts_requests_only")
        if checked["interface_id"] != INTERFACE_ID:
            raise TIISValidationError("unexpected_interface")
        if checked["interface_version"] != INTERFACE_VERSION:
            raise TIISValidationError("unsupported_interface_version")

        operation = checked["operation"]
        if operation not in _ALLOWED_OPERATIONS:
            return self._response(
                checked, sender, "rejected", {},
                {"code": "operation.unsupported", "message": "The requested catalog operation is not supported.", "retryable": False},
                now,
            )

        payload = checked["payload"]
        if not isinstance(payload, Mapping):
            raise TIISValidationError("payload_must_be_object")

        try:
            if operation == "tool.get":
                if set(payload) != {"tool_id", "version"}:
                    raise TIISValidationError("tool_get_payload_fields_invalid")
                tool_id, version = payload["tool_id"], payload["version"]
                if not isinstance(tool_id, str) or not isinstance(version, str):
                    raise TIISValidationError("tool_get_payload_invalid")
                record = self._catalog.get(tool_id, version)
                if record is None:
                    return self._response(
                        checked, sender, "rejected", {},
                        {"code": "tool.not-found", "message": "The requested tool version was not found.", "retryable": False},
                        now,
                    )
                result = {"tool": self._jsonable(record)}
            else:
                if set(payload) - {"status", "category"}:
                    raise TIISValidationError("tool_list_payload_fields_invalid")
                status = payload.get("status")
                category = payload.get("category")
                if status is not None and not isinstance(status, str):
                    raise TIISValidationError("tool_list_status_invalid")
                if category is not None and not isinstance(category, str):
                    raise TIISValidationError("tool_list_category_invalid")
                result = {"tools": self._jsonable(self._catalog.list_tools(status=status, category=category))}
            return self._response(checked, sender, "succeeded", result, None, now)
        except TIISValidationError:
            raise
        except (ValueError, KeyError):
            return self._response(
                checked, sender, "rejected", {},
                {"code": "request.invalid", "message": "The catalog request is invalid.", "retryable": False},
                now,
            )
        except Exception:
            return self._response(
                checked, sender, "failed", {},
                {"code": "catalog.unavailable", "message": "The tool catalog could not complete the request.", "retryable": True},
                now,
            )

    def _response(
        self,
        request: Mapping[str, Any],
        recipient: Mapping[str, str],
        outcome: str,
        payload: Mapping[str, Any],
        error: Mapping[str, Any] | None,
        now: datetime | None,
    ) -> dict[str, Any]:
        response: dict[str, Any] = {
            "protocol": "TIIS",
            "protocol_version": "0.1",
            "message_type": "response",
            "message_id": str(uuid4()),
            "correlation_id": request["correlation_id"],
            "in_reply_to": request["message_id"],
            "sender": self._local_component,
            "recipient": dict(recipient),
            "interface_id": INTERFACE_ID,
            "interface_version": INTERFACE_VERSION,
            "issued_at": self._issued_at(now),
            "outcome": outcome,
            "payload": dict(payload),
        }
        if error is not None:
            response["error"] = dict(error)
        if "trace" in request:
            response["trace"] = dict(request["trace"])
        return response
