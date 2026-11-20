"""OBIS bridge adapter for explicitly injected, authenticated peer clients.

This module contains no network stack and no credential loader. The caller must
inject an OBIS client whose transport authenticates the remote peer, verifies
response signatures, enforces expiry/replay rules, and keeps provider secrets
outside ECOSCAN. The adapter only maps a validated OBIS capability response
into ECOSCAN's bounded measurement contract.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol
from urllib.parse import urlparse

from .contracts import AdapterContractError, AdapterResult, ScanContext, TransportOutcomeUnknown
from .models import SourceDescriptor


CAPABILITY_ID = "ecoscan.inventory.read"
CAPABILITY_VERSION = "1.0"
REQUIRED_SCOPE = "ecoscan:inventory:read"
SUPPORTED_MEASUREMENTS = {"logical_bytes", "file_count"}


class OBISInvoker(Protocol):
    local_peer_id: str
    remote_peer_id: str

    def invoke(
        self,
        endpoint: str,
        capability_id: str,
        capability_version: str,
        payload: dict[str, Any],
        scopes: set[str] | frozenset[str] | None = None,
        deadline: float | None = None,
    ) -> dict[str, Any]: ...


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 128:
        raise AdapterContractError(f"{label} must be a non-empty identifier")
    if any(ch.isspace() for ch in value):
        raise AdapterContractError(f"{label} must not contain whitespace")
    return value


def _nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise AdapterContractError(f"{label} must be a non-negative integer")
    return value


class OBISBridgeAdapter:
    """Read-only inventory adapter over one explicitly configured OBIS peer."""

    adapter_id = "obis_bridge"
    version = "0.1.0"

    def __init__(self, client: OBISInvoker, endpoint: str) -> None:
        if client is None or not callable(getattr(client, "invoke", None)):
            raise ValueError("an authenticated OBIS client is required")
        parsed = urlparse(endpoint)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname:
            raise ValueError("OBIS endpoint must be an absolute HTTP(S) URL")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("OBIS endpoint must not contain embedded credentials")
        if parsed.query or parsed.fragment:
            raise ValueError("OBIS endpoint must not contain query or fragment data")
        self.client = client
        self.endpoint = endpoint.rstrip("/")

    def validate_config(self, source_descriptor: SourceDescriptor) -> None:
        if source_descriptor.source_type != "obis_bridge":
            raise AdapterContractError("OBIS adapter accepts obis_bridge sources only")
        peer_id = _identifier(source_descriptor.locator, "OBIS peer ID")
        if peer_id != self.client.remote_peer_id:
            raise AdapterContractError("OBIS peer identity does not match the registered source")
        _identifier(self.client.local_peer_id, "local OBIS peer ID")
        if not source_descriptor.expected_measurements or not set(source_descriptor.expected_measurements).issubset(SUPPORTED_MEASUREMENTS):
            raise AdapterContractError("OBIS source declares unsupported inventory measurements")
        if REQUIRED_SCOPE not in self._client_scopes():
            raise AdapterContractError("OBIS client does not hold the required read-only inventory scope")

    def _client_scopes(self) -> frozenset[str]:
        scopes = getattr(self.client, "scopes", None)
        if not isinstance(scopes, (set, frozenset)):
            return frozenset()
        return frozenset(item for item in scopes if isinstance(item, str))

    def scan(self, context: ScanContext) -> AdapterResult:
        # Charge the request page before making a remote call. Every provider
        # page/item reported by the Bridge is charged against the same local budget.
        context.guard.consume_page()
        try:
            response = self.client.invoke(
                self.endpoint,
                CAPABILITY_ID,
                CAPABILITY_VERSION,
                {
                    "project_id": context.project_id,
                    "source_id": context.source.source_id,
                    "measurement_kinds": list(context.source.expected_measurements),
                },
                scopes={REQUIRED_SCOPE},
                deadline=context.guard.deadline,
            )
        except Exception as exc:
            # Once invoke() has begun, an exception without a verified,
            # pre-execution rejection cannot prove that the remote capability
            # did not run. Never turn that uncertainty into a retryable FAILED.
            code = getattr(exc, "code", None)
            definitely_not_executed = {
                "authorization.denied", "capability.unknown", "identity.unknown_peer",
                "request.expired", "request.replay_detected",
            }
            if code in definitely_not_executed:
                raise
            raise TransportOutcomeUnknown("OBIS request outcome is unknown") from exc
        context.guard.check_deadline()
        if not isinstance(response, Mapping):
            raise AdapterContractError("OBIS response must be an object")
        sender = response.get("sender")
        recipient = response.get("recipient")
        if (
            not isinstance(sender, Mapping)
            or sender.get("peer_id") != context.source.locator
            or not isinstance(recipient, Mapping)
            or recipient.get("peer_id") != self.client.local_peer_id
            or response.get("outcome") != "succeeded"
        ):
            raise AdapterContractError("OBIS response identity or outcome is invalid")
        result = response.get("result")
        if not isinstance(result, Mapping):
            raise AdapterContractError("OBIS capability result must be an object")

        required = {
            "project_id", "source_id", "coverage_state", "items_seen",
            "pages_seen", "measurements", "source_timestamp", "limitations",
            "evidence_ref",
        }
        if set(result) != required:
            raise AdapterContractError("OBIS inventory result has unknown or missing fields")
        if result["project_id"] != context.project_id or result["source_id"] != context.source.source_id:
            raise AdapterContractError("OBIS inventory result crosses project/source boundary")
        state = result["coverage_state"]
        if state not in {"COMPLETE", "PARTIAL"}:
            raise AdapterContractError("OBIS inventory coverage state is invalid")
        items_seen = _nonnegative_int(result["items_seen"], "items_seen")
        pages_seen = _nonnegative_int(result["pages_seen"], "pages_seen")
        if pages_seen < 1:
            raise AdapterContractError("OBIS inventory must report at least one page")
        for _ in range(pages_seen - 1):
            context.guard.consume_page()
        for _ in range(items_seen):
            context.guard.consume_item()

        values = result["measurements"]
        if not isinstance(values, Mapping) or set(values) != set(context.source.expected_measurements):
            raise AdapterContractError("OBIS measurement set does not match the registered source")
        limitations = result["limitations"]
        if not isinstance(limitations, (list, tuple)) or any(not isinstance(x, str) or not x for x in limitations):
            raise AdapterContractError("OBIS limitations must be non-empty strings")
        source_timestamp = result["source_timestamp"]
        if source_timestamp is not None and (not isinstance(source_timestamp, str) or not source_timestamp):
            raise AdapterContractError("OBIS source_timestamp must be null or a non-empty string")
        evidence_ref = result["evidence_ref"]
        if evidence_ref is not None and (not isinstance(evidence_ref, str) or not evidence_ref):
            raise AdapterContractError("OBIS evidence_ref must be null or a non-empty string")

        measured_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        common = {
            "schema_version": "0.1",
            "project_id": context.project_id,
            "source_id": context.source.source_id,
            "measured_at": measured_at,
            "source_timestamp": source_timestamp,
            "method": "obis-bridge-inventory",
            "adapter_id": self.adapter_id,
            "adapter_version": self.version,
            "coverage_state": state,
            "confidence": "MEDIUM" if state == "COMPLETE" else "LOW",
            "limitations": list(limitations),
            "evidence_ref": evidence_ref,
            "checkpoint_ref": None,
        }
        units = {"logical_bytes": "byte", "file_count": "file"}
        measurements = []
        for kind in context.source.expected_measurements:
            value = _nonnegative_int(values[kind], kind)
            measurements.append({
                **common,
                "measurement_id": str(uuid.uuid4()),
                "kind": kind,
                "value": value,
                "unit": units[kind],
            })
        return AdapterResult(
            state,
            tuple(measurements),
            items_seen,
            pages_seen,
            None,
            tuple(limitations),
            None,
        )
