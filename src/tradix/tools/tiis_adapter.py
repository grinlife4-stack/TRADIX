"""TIIS 0.1 codec for the bounded Tool Adapter contract.

This module validates and serializes invocations/results only. It does not run
an adapter, start a worker, create a sandbox, or schedule a job.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any
from uuid import UUID, uuid4

from tradix.tiis import TIISValidator
from .adapter import AdapterResult, ResourceLimits, ToolInvocation


INTERFACE_ID = "tool.adapter"
INTERFACE_VERSION = "0.1.0"


class ToolAdapterTIISCodecError(ValueError):
    """Raised when an adapter invocation/result does not match its TIIS contract."""


def _identity(value: Mapping[str, Any], name: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ToolAdapterTIISCodecError(f"{name}_identity_invalid")
    allowed = {"project_id", "component_id", "instance_id"}
    if set(value) - allowed or not {"project_id", "component_id"}.issubset(value):
        raise ToolAdapterTIISCodecError(f"{name}_identity_invalid")
    return {key: value[key] for key in ("project_id", "component_id", "instance_id") if key in value}


def _timestamp(now: datetime | None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now_must_be_timezone_aware")
    return current.astimezone(timezone.utc)


def invocation_to_tiis(
    invocation: ToolInvocation,
    *,
    sender_component: Mapping[str, Any],
    recipient_component: Mapping[str, Any],
    supported_job_types: tuple[str, ...],
    ttl_seconds: int = 60,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Create a TIIS request from a validated bounded invocation."""
    if not isinstance(invocation, ToolInvocation):
        raise TypeError("invocation_must_be_ToolInvocation")
    invocation.validate(supported_job_types)
    if not isinstance(ttl_seconds, int) or not 1 <= ttl_seconds <= 3600:
        raise ValueError("ttl_seconds_must_be_between_1_and_3600")
    sender = _identity(sender_component, "sender")
    recipient = _identity(recipient_component, "recipient")
    issued = _timestamp(now)
    envelope = {
        "protocol": "TIIS",
        "protocol_version": "0.1",
        "message_type": "request",
        "message_id": str(uuid4()),
        "correlation_id": str(uuid4()),
        "sender": sender,
        "recipient": recipient,
        "interface_id": INTERFACE_ID,
        "interface_version": INTERFACE_VERSION,
        "operation": "invoke",
        "issued_at": issued.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "expires_at": (issued + timedelta(seconds=ttl_seconds)).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "idempotency_key": "tiis-" + sha256(invocation.idempotency_key.encode("utf-8")).hexdigest(),
        "payload": {
            "invocation": {
                "run_id": invocation.run_id,
                "tool_id": invocation.tool_id,
                "tool_version": invocation.tool_version,
                "job_type": invocation.job_type,
                "source_commit_sha": invocation.source_commit_sha,
                "input_refs": list(invocation.input_refs),
                "idempotency_key": invocation.idempotency_key,
                "limits": {
                    "cpu_millis": invocation.limits.cpu_millis,
                    "memory_mb": invocation.limits.memory_mb,
                    "timeout_seconds": invocation.limits.timeout_seconds,
                    "network_enabled": invocation.limits.network_enabled,
                    "writable_workspace": invocation.limits.writable_workspace,
                },
            }
        },
    }
    return envelope


def invocation_from_tiis(
    envelope: Mapping[str, Any],
    *,
    validator: TIISValidator,
    authenticated_sender: Mapping[str, Any],
    expected_recipient: Mapping[str, Any],
    supported_job_types: tuple[str, ...],
    now: datetime | None = None,
) -> ToolInvocation:
    """Validate TIIS authorization and reconstruct a bounded invocation."""
    checked = validator.validate(
        envelope,
        authenticated_sender=authenticated_sender,
        expected_recipient=expected_recipient,
        now=now,
    )
    if checked["message_type"] != "request":
        raise ToolAdapterTIISCodecError("invocation_request_required")
    if checked["interface_id"] != INTERFACE_ID or checked["interface_version"] != INTERFACE_VERSION:
        raise ToolAdapterTIISCodecError("unsupported_tool_adapter_interface")
    if checked["operation"] != "invoke":
        raise ToolAdapterTIISCodecError("unsupported_tool_adapter_operation")

    payload = checked["payload"]
    if not isinstance(payload, Mapping) or set(payload) != {"invocation"}:
        raise ToolAdapterTIISCodecError("invocation_payload_invalid")
    data = payload["invocation"]
    required = {
        "run_id", "tool_id", "tool_version", "job_type", "source_commit_sha",
        "input_refs", "idempotency_key", "limits",
    }
    if not isinstance(data, Mapping) or set(data) != required:
        raise ToolAdapterTIISCodecError("invocation_fields_invalid")
    expected_idempotency = "tiis-" + sha256(str(data.get("idempotency_key", "")).encode("utf-8")).hexdigest()
    if checked.get("idempotency_key") != expected_idempotency:
        raise ToolAdapterTIISCodecError("idempotency_binding_mismatch")
    limits_data = data["limits"]
    limit_fields = {
        "cpu_millis", "memory_mb", "timeout_seconds", "network_enabled", "writable_workspace"
    }
    if not isinstance(limits_data, Mapping) or set(limits_data) != limit_fields:
        raise ToolAdapterTIISCodecError("resource_limits_invalid")
    if not isinstance(data["input_refs"], list):
        raise ToolAdapterTIISCodecError("input_refs_must_be_array")

    try:
        limits = ResourceLimits(**dict(limits_data))
        invocation = ToolInvocation(
            run_id=data["run_id"],
            tool_id=data["tool_id"],
            tool_version=data["tool_version"],
            job_type=data["job_type"],
            source_commit_sha=data["source_commit_sha"],
            input_refs=tuple(data["input_refs"]),
            idempotency_key=data["idempotency_key"],
            limits=limits,
        )
        invocation.validate(supported_job_types)
    except (TypeError, ValueError) as exc:
        raise ToolAdapterTIISCodecError("invocation_contract_rejected") from exc
    return invocation


def result_to_tiis_event(
    result: AdapterResult,
    invocation: ToolInvocation,
    *,
    sender_component: Mapping[str, Any],
    recipient_component: Mapping[str, Any],
    correlation_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Serialize a verified adapter result as a TIIS event; performs no execution."""
    if not isinstance(result, AdapterResult) or not isinstance(invocation, ToolInvocation):
        raise TypeError("result_and_invocation_types_invalid")
    result.validate(invocation)
    sender = _identity(sender_component, "sender")
    recipient = _identity(recipient_component, "recipient")
    try:
        UUID(correlation_id)
    except (TypeError, ValueError) as exc:
        raise ToolAdapterTIISCodecError("correlation_id_must_be_uuid") from exc
    issued = _timestamp(now)
    return {
        "protocol": "TIIS",
        "protocol_version": "0.1",
        "message_type": "event",
        "message_id": str(uuid4()),
        "correlation_id": correlation_id,
        "sender": sender,
        "recipient": recipient,
        "interface_id": INTERFACE_ID,
        "interface_version": INTERFACE_VERSION,
        "event_type": "tool.adapter.result",
        "issued_at": issued.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "payload": {
            "run_id": result.run_id,
            "status": result.status,
            "started_at": result.started_at,
            "finished_at": result.finished_at,
            "source_commit_sha": result.source_commit_sha,
            "output_refs": list(result.output_refs),
            "evidence_refs": list(result.evidence_refs),
            "error_code": result.error_code,
            "error_message": result.error_message,
        },
    }
