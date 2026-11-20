"""Fail-closed single-source scan orchestration."""

from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from .contracts import Adapter, AdapterContractError, AdapterResult, BudgetExceeded, BudgetGuard, ScanContext
from .controls import ExecutionGate
from .models import ProjectRegistry, SourceDescriptor
from .store import ProjectStore, StoreError

IDENTIFIER = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")
UNIT_BY_KIND = {
    "logical_bytes": "byte",
    "allocated_bytes": "byte",
    "physical_bytes": "byte",
    "capacity_bytes": "byte",
    "object_count": "object",
    "file_count": "file",
    "provider_reported_usage": "provider_unit",
}
MEASUREMENT_KEYS = {
    "schema_version", "measurement_id", "project_id", "source_id", "kind", "value", "unit",
    "measured_at", "source_timestamp", "method", "adapter_id", "adapter_version",
    "coverage_state", "confidence", "limitations", "evidence_ref", "checkpoint_ref",
}
CONFIDENCE = {"HIGH", "MEDIUM", "LOW", "UNVERIFIED"}


class ScanError(ValueError):
    """Raised when a requested source cannot be selected or a result cannot be stored."""


@dataclass(frozen=True, slots=True)
class ScanOutcome:
    scan_id: str
    project_id: str
    source_id: str
    coverage_state: str
    reason_code: str | None
    measurements_written: int


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _timestamp(value: Any, name: str, nullable: bool = False) -> None:
    if value is None and nullable:
        return
    if not isinstance(value, str) or not value:
        raise AdapterContractError(f"{name} must be an ISO-8601 timestamp")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise AdapterContractError(f"{name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AdapterContractError(f"{name} must include a timezone")


def _validate_measurement(
    record: Mapping[str, Any],
    registry: ProjectRegistry,
    source: SourceDescriptor,
    adapter: Adapter,
    coverage_state: str,
) -> dict[str, Any]:
    if not isinstance(record, Mapping) or set(record) != MEASUREMENT_KEYS:
        raise AdapterContractError("measurement has unknown or missing fields")
    if record["schema_version"] != "0.1":
        raise AdapterContractError("unsupported measurement schema_version")
    if record["project_id"] != registry.project_id or record["source_id"] != source.source_id:
        raise AdapterContractError("measurement crosses project/source boundary")
    measurement_id = record["measurement_id"]
    if not isinstance(measurement_id, str) or not IDENTIFIER.fullmatch(measurement_id):
        raise AdapterContractError("invalid measurement_id")
    kind = record["kind"]
    if kind not in source.expected_measurements or kind not in UNIT_BY_KIND:
        raise AdapterContractError("measurement kind was not declared by the source")
    if record["unit"] != UNIT_BY_KIND[kind]:
        raise AdapterContractError("measurement unit does not match measurement kind")
    value = record["value"]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise AdapterContractError("measurement value must be finite and non-negative")
    if kind != "provider_reported_usage" and not isinstance(value, int):
        raise AdapterContractError("byte and count measurements must be integers")
    _timestamp(record["measured_at"], "measured_at")
    _timestamp(record["source_timestamp"], "source_timestamp", nullable=True)
    if not isinstance(record["method"], str) or not record["method"]:
        raise AdapterContractError("measurement method is required")
    if record["adapter_id"] != adapter.adapter_id or record["adapter_version"] != adapter.version:
        raise AdapterContractError("measurement adapter identity mismatch")
    if record["coverage_state"] != coverage_state or coverage_state not in {"COMPLETE", "PARTIAL"}:
        raise AdapterContractError("measurement coverage state mismatch")
    if record["confidence"] not in CONFIDENCE:
        raise AdapterContractError("invalid measurement confidence")
    if (
        not isinstance(record["limitations"], (list, tuple))
        or any(not isinstance(item, str) or not item for item in record["limitations"])
    ):
        raise AdapterContractError("limitations must be non-empty strings")
    for key in ("evidence_ref", "checkpoint_ref"):
        if record[key] is not None and (not isinstance(record[key], str) or not record[key]):
            raise AdapterContractError(f"{key} must be null or a non-empty string")
    return dict(record)


class ScanRunner:
    def __init__(
        self,
        registry: ProjectRegistry,
        gate: ExecutionGate,
        adapters: Mapping[str, Adapter],
        store: ProjectStore,
    ) -> None:
        if store.project_id != registry.project_id:
            raise ScanError("project store does not match project registry")
        self.registry = registry
        self.gate = gate
        self.adapters = dict(adapters)
        self.store = store

    def _persist_gate_result(
        self,
        source: SourceDescriptor,
        actor_id: str,
        scan_id: str,
        started_at: str,
        state: str,
        reason: str,
    ) -> ScanOutcome:
        adapter = self.adapters.get(source.adapter_id)
        record = {
            "schema_version": "0.1",
            "scan_id": scan_id,
            "project_id": self.registry.project_id,
            "source_id": source.source_id,
            "requested_scope": f"source:{source.source_id}",
            "coverage_state": state,
            "started_at": started_at,
            "finished_at": _now(),
            "actor_id": actor_id,
            "adapter_id": source.adapter_id,
            "adapter_version": source.adapter_version,
            "items_seen": 0,
            "pages_seen": 0,
            "reason_code": reason,
            "limitations": [],
            "checkpoint_ref": None,
        }
        self.store.append_scan(record, [])
        return ScanOutcome(scan_id, self.registry.project_id, source.source_id, state, reason, 0)

    def run(
        self,
        source_id: str,
        actor_id: str,
        checkpoint: Mapping[str, Any] | None = None,
    ) -> ScanOutcome:
        if not isinstance(actor_id, str) or not IDENTIFIER.fullmatch(actor_id):
            raise ScanError("actor_id must be a valid identifier")
        matches = [source for source in self.registry.sources if source.source_id == source_id]
        if len(matches) != 1:
            raise ScanError("source_id is not uniquely registered in this project")
        source = matches[0]
        scan_id = str(uuid.uuid4())
        started_at = _now()

        decision = self.gate.evaluate(self.registry, source, actor_id)
        if not decision.allowed:
            return self._persist_gate_result(
                source, actor_id, scan_id, started_at,
                decision.coverage_state or "NOT_AUTHORIZED",
                decision.reason_code or "authorization_denied",
            )

        adapter = self.adapters.get(source.adapter_id)
        if adapter is None:
            return self._persist_gate_result(
                source, actor_id, scan_id, started_at, "NOT_CONFIGURED", "adapter_not_registered"
            )
        if adapter.adapter_id != source.adapter_id or adapter.version != source.adapter_version:
            return self._persist_gate_result(
                source, actor_id, scan_id, started_at, "FAILED", "adapter_version_mismatch"
            )

        guard = BudgetGuard(source.budget)
        context = ScanContext(self.registry.project_id, actor_id, source, source.budget, guard, checkpoint)
        try:
            adapter.validate_config(source)
            result = adapter.scan(context)
            if not isinstance(result, AdapterResult):
                raise AdapterContractError("adapter must return AdapterResult")
            if result.coverage_state not in {"COMPLETE", "PARTIAL", "FAILED"}:
                raise AdapterContractError("invalid adapter coverage state")
            if result.items_seen != guard.items_seen or result.pages_seen != guard.pages_seen:
                raise AdapterContractError("adapter result counters do not match budget guard")
            if result.items_seen > source.budget.max_items or result.pages_seen > source.budget.max_pages:
                raise AdapterContractError("adapter exceeded declared scan budget")
            if len(result.measurements) > result.items_seen:
                raise AdapterContractError("measurement count exceeds observed item count")
            if result.coverage_state == "FAILED" and result.measurements:
                raise AdapterContractError("failed scan cannot publish measurements")
            measurements = [
                _validate_measurement(item, self.registry, source, adapter, result.coverage_state)
                for item in result.measurements
            ]
            if len({item["measurement_id"] for item in measurements}) != len(measurements):
                raise AdapterContractError("measurement IDs must be unique within a scan")
            if result.checkpoint is not None and not isinstance(result.checkpoint, Mapping):
                raise AdapterContractError("checkpoint must be an object")
            coverage_record = {
                "schema_version": "0.1",
                "scan_id": scan_id,
                "project_id": self.registry.project_id,
                "source_id": source.source_id,
                "requested_scope": f"source:{source.source_id}",
                "coverage_state": result.coverage_state,
                "started_at": started_at,
                "finished_at": _now(),
                "actor_id": actor_id,
                "adapter_id": adapter.adapter_id,
                "adapter_version": adapter.version,
                "items_seen": result.items_seen,
                "pages_seen": result.pages_seen,
                "reason_code": result.reason_code,
                "limitations": list(result.limitations),
                "checkpoint_ref": scan_id if result.checkpoint is not None else None,
            }
            if result.checkpoint is not None:
                self.store.save_checkpoint(source.source_id, scan_id, result.checkpoint, coverage_record["finished_at"])
            self.store.append_scan(coverage_record, measurements)
            return ScanOutcome(
                scan_id, self.registry.project_id, source.source_id,
                result.coverage_state, result.reason_code, len(measurements)
            )
        except BudgetExceeded:
            state = "PARTIAL" if guard.items_seen else "FAILED"
            reason = "budget_exhausted"
        except AdapterContractError:
            state = "FAILED"
            reason = "adapter_contract_violation"
        except Exception:
            state = "FAILED"
            reason = "adapter_execution_failed"

        failed_record = {
            "schema_version": "0.1",
            "scan_id": scan_id,
            "project_id": self.registry.project_id,
            "source_id": source.source_id,
            "requested_scope": f"source:{source.source_id}",
            "coverage_state": state,
            "started_at": started_at,
            "finished_at": _now(),
            "actor_id": actor_id,
            "adapter_id": adapter.adapter_id,
            "adapter_version": adapter.version,
            "items_seen": guard.items_seen,
            "pages_seen": guard.pages_seen,
            "reason_code": reason,
            "limitations": ["No complete measurement set was committed for this scan attempt."],
            "checkpoint_ref": None,
        }
        self.store.append_scan(failed_record, [])
        return ScanOutcome(scan_id, self.registry.project_id, source.source_id, state, reason, 0)
