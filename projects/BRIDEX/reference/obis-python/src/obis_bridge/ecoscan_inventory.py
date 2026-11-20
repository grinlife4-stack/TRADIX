"""ECOSCAN read-only inventory capability for an independently operated OBIS Bridge."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from .peer import OBISPeer

CAPABILITY_ID = "ecoscan.inventory.read"
CAPABILITY_VERSION = "1.0"
REQUIRED_SCOPE = "ecoscan:inventory:read"
SUPPORTED_KINDS = frozenset({"logical_bytes", "file_count"})


def register_ecoscan_inventory_capability(
    peer: OBISPeer,
    inventory_provider: Callable[[str, str, tuple[str, ...]], Mapping[str, Any]],
) -> None:
    """Register a read-only inventory capability with credential-bound resources.

    Each Credential on the OBISPeer must explicitly list allowed_resources as
    (project_id, source_id) tuples. The OBISPeer enforces that grant before this
    handler is called. The provider must perform metadata-only reads and must
    not modify the external project.
    """
    if not callable(inventory_provider):
        raise ValueError("inventory_provider must be callable")

    def handle(payload: dict[str, Any]) -> dict[str, Any]:
        if set(payload) != {"project_id", "source_id", "measurement_kinds"}:
            raise ValueError("inventory request has unknown or missing fields")
        project_id = payload["project_id"]
        source_id = payload["source_id"]
        kinds = payload["measurement_kinds"]
        if (
            not isinstance(project_id, str) or not project_id
            or not isinstance(source_id, str) or not source_id
            or not isinstance(kinds, list) or not kinds
            or any(not isinstance(kind, str) or kind not in SUPPORTED_KINDS for kind in kinds)
            or len(set(kinds)) != len(kinds)
        ):
            raise ValueError("invalid project/source or requested measurement kinds")

        raw = inventory_provider(project_id, source_id, tuple(kinds))
        if not isinstance(raw, Mapping):
            raise ValueError("inventory provider must return an object")
        expected = {
            "coverage_state", "items_seen", "pages_seen", "measurements",
            "source_timestamp", "limitations", "evidence_ref",
        }
        if set(raw) != expected:
            raise ValueError("inventory provider result has unknown or missing fields")
        state = raw["coverage_state"]
        if state not in {"COMPLETE", "PARTIAL"}:
            raise ValueError("inventory provider returned invalid coverage state")
        for field in ("items_seen", "pages_seen"):
            value = raw[field]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{field} must be a non-negative integer")
        if raw["pages_seen"] < 1:
            raise ValueError("pages_seen must be at least one")
        values = raw["measurements"]
        if not isinstance(values, Mapping) or set(values) != set(kinds):
            raise ValueError("inventory provider measurement set does not match request")
        for kind, value in values.items():
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{kind} must be a non-negative integer")
        timestamp = raw["source_timestamp"]
        if timestamp is not None and (not isinstance(timestamp, str) or not timestamp):
            raise ValueError("source_timestamp must be null or a non-empty string")
        limitations = raw["limitations"]
        if not isinstance(limitations, list) or any(not isinstance(x, str) or not x for x in limitations):
            raise ValueError("limitations must be an array of non-empty strings")
        evidence_ref = raw["evidence_ref"]
        if evidence_ref is not None and (not isinstance(evidence_ref, str) or not evidence_ref):
            raise ValueError("evidence_ref must be null or a non-empty string")
        return {
            "project_id": project_id,
            "source_id": source_id,
            "coverage_state": state,
            "items_seen": raw["items_seen"],
            "pages_seen": raw["pages_seen"],
            "measurements": dict(values),
            "source_timestamp": timestamp,
            "limitations": list(limitations),
            "evidence_ref": evidence_ref,
        }

    peer.register_capability(
        CAPABILITY_ID,
        CAPABILITY_VERSION,
        {REQUIRED_SCOPE},
        handle,
        resource_binding=True,
    )
