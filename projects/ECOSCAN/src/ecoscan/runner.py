"""Fail-closed single-source scan orchestration."""

from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from .contracts import Adapter, AdapterContractError, AdapterResult, AuthorizationRevoked, BudgetExceeded, BudgetGuard, ScanContext, TransportOutcomeUnknown
from .controls import ExecutionGate
from .models import ProjectRegistry, SourceDescriptor
from .store import ProjectStore

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
    """Raised when a requested source cannot be selected or the project boundary is invalid."""


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
    if not isinstance(kind, str) or kind not in source.expected_measurements or kind not in UNIT_BY_KIND:
        raise AdapterContractError("measurement kind was not declared by the source")
    if record["unit"] != UNIT_BY_KIND[kind]:
        raise AdapterContractError("measurement unit does not match measurement kind")
    value = record["value"]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise AdapterContractError("measurement value must be non-negative numeric data")
    if isinstance(value, float) and not math.isfinite(value):
        raise AdapterContractError("measurement value must be finite")
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
    if not isinstance(record["confidence"], str) or record["confidence"] not in CONFIDENCE:
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
    """Runs exactly one registered source; it never discovers or widens scope."""

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

    def _coverage(
        self,
        source: SourceDescriptor,
        actor_id: str,
        scan_id: str,
        started_at: str,
        state: str,
        reason: str | None,
        adapter_id: str | None = None,
        adapter_version: str | None = None,
        items_seen: int = 0,
        pages_seen: int = 0,
        limitations: tuple[str, ...] | list[str] = (),
        checkpoint_ref: str | None = None,
    ) -> dict[str, Any]:
        return {
            "schema_version": "0.2" if state == "INDETERMINATE" else "0.1",
            "scan_id": scan_id,
            "project_id": self.registry.project_id,
            "source_id": source.source_id,
            "requested_scope": f"source:{source.source_id}",
            "coverage_state": state,
            "started_at": started_at,
            "finished_at": _now(),
            "actor_id": actor_id,
            "adapter_id": adapter_id or source.adapter_id,
            "adapter_version": adapter_version or source.adapter_version,
            "items_seen": items_seen,
            "pages_seen": pages_seen,
            "reason_code": reason,
            "limitations": list(limitations),
            "checkpoint_ref": checkpoint_ref,
        }

    def _record_without_adapter(
        self,
        source: SourceDescriptor,
        actor_id: str,
        scan_id: str,
        started_at: str,
        state: str,
        reason: str,
    ) -> ScanOutcome:
        record = self._coverage(source, actor_id, scan_id, started_at, state, reason)
        self.store.append_scan(record, [])
        return ScanOutcome(scan_id, self.registry.project_id, source.source_id, state, reason, 0)

    def project_reconciled_measurements(self, source_id: str | None = None) -> list[dict[str, Any]]:
        """Materialize successful recovery events as standard Measurements, idempotently."""
        sources = {item.source_id: item for item in self.registry.sources}
        projected = []
        for event in self.store.list_operation_reconciliations(source_id):
            if event["outcome"] != "SUCCEEDED":
                continue
            source = sources.get(event["source_id"])
            if source is None:
                projected.append({"reconciliation_id": event["reconciliation_id"], "state": "PROJECTION_REJECTED",
                                  "reason_code": "source_not_registered"})
                continue
            result = event["result"]
            values = result.get("measurements") if isinstance(result, Mapping) else None
            if not isinstance(values, Mapping) or set(values) != set(source.expected_measurements):
                projected.append({"reconciliation_id": event["reconciliation_id"], "state": "PROJECTION_REJECTED",
                                  "reason_code": "measurement_set_mismatch"})
                continue
            coverage_state = result.get("coverage_state")
            if coverage_state not in {"COMPLETE", "PARTIAL"}:
                projected.append({"reconciliation_id": event["reconciliation_id"], "state": "PROJECTION_REJECTED",
                                  "reason_code": "invalid_coverage_state"})
                continue
            measurements = []
            try:
                for kind in sorted(values):
                    value = values[kind]
                    if (kind not in UNIT_BY_KIND or kind not in source.expected_measurements
                            or isinstance(value, bool) or not isinstance(value, int) or value < 0):
                        raise ScanError("recovered measurement value or kind is invalid")
                    measured = {
                        "schema_version": "0.1",
                        "measurement_id": str(uuid.uuid5(
                            uuid.NAMESPACE_URL,
                            f"ecoscan:reconciliation:{event['reconciliation_id']}:{kind}",
                        )),
                        "project_id": self.registry.project_id,
                        "source_id": source.source_id,
                        "kind": kind,
                        "value": value,
                        "unit": UNIT_BY_KIND[kind],
                        "measured_at": event["recorded_at"],
                        "source_timestamp": result.get("source_timestamp"),
                        "method": f"obis_v0.2_status_reconciliation:{event['reconciliation_id']}",
                        "adapter_id": source.adapter_id,
                        "adapter_version": source.adapter_version,
                        "coverage_state": coverage_state,
                        "confidence": "UNVERIFIED",
                        "limitations": list(result.get("limitations", [])) + ["RECOVERED_BY_STATUS_RECONCILIATION"],
                        "evidence_ref": result.get("evidence_ref"),
                        "checkpoint_ref": None,
                        "scan_id": event["scan_id"],
                    }
                    _timestamp(measured["measured_at"], "measured_at")
                    _timestamp(measured["source_timestamp"], "source_timestamp", nullable=True)
                    measurements.append(measured)
                count = self.store.append_reconciliation_measurements(
                    reconciliation_id=event["reconciliation_id"],
                    measurements=measurements,
                )
                projected.append({"reconciliation_id": event["reconciliation_id"], "state": "PROJECTED",
                                  "measurements_inserted": count})
            except Exception as exc:
                projected.append({"reconciliation_id": event["reconciliation_id"], "state": "PROJECTION_PENDING",
                                  "reason_code": type(exc).__name__})
        return projected

    def reconcile_pending(self, source_id: str, actor_id: str) -> list[dict[str, Any]]:
        """Reconcile durable OBIS operations by status lookup only; never invoke again."""
        if not isinstance(actor_id, str) or not IDENTIFIER.fullmatch(actor_id):
            raise ScanError("actor_id must be a valid identifier")
        matches = [item for item in self.registry.sources if item.source_id == source_id]
        if len(matches) != 1:
            raise ScanError("source_id is not uniquely registered in this project")
        source = matches[0]
        adapter = self.adapters.get(source.adapter_id)
        if adapter is None or adapter.adapter_id != source.adapter_id or adapter.version != source.adapter_version:
            raise ScanError("the configured reconciliation adapter is unavailable or mismatched")
        validate_config = getattr(adapter, "validate_config", None)
        reconcile = getattr(adapter, "reconcile_operation", None)
        if not callable(validate_config) or not callable(reconcile):
            raise ScanError("source adapter does not support durable operation reconciliation")
        validate_config(source)
        self.project_reconciled_measurements(source_id)
        outcomes: list[dict[str, Any]] = []
        def still_authorized() -> bool:
            return self.gate.evaluate(self.registry, source, actor_id).allowed

        # One shared guard bounds the complete recovery batch, not each
        # individual status request independently.
        guard = BudgetGuard(source.budget, before_page=still_authorized)
        for intent in self.store.list_unresolved_operation_intents(source_id):
            decision = self.gate.evaluate(self.registry, source, actor_id)
            if not decision.allowed:
                outcomes.append({"scan_id": intent["scan_id"], "state": "UNRESOLVED",
                                 "reason_code": decision.reason_code or "authorization_denied"})
                break
            context = ScanContext(
                self.registry.project_id, actor_id, source, source.budget, guard,
                scan_id=intent["scan_id"], operation_intent=intent,
            )
            try:
                response = reconcile(context, intent)
                guard.check_deadline()
                if not isinstance(response, Mapping) or not isinstance(response.get("result"), Mapping):
                    raise AdapterContractError("reconciliation response has no committed result")
                result = response["result"]
                required = {
                    "project_id", "source_id", "coverage_state", "items_seen",
                    "pages_seen", "measurements", "source_timestamp", "limitations",
                    "evidence_ref",
                }
                if set(result) != required:
                    raise AdapterContractError("recovered OBIS result has unknown or missing fields")
                if result["project_id"] != self.registry.project_id or result["source_id"] != source.source_id:
                    raise AdapterContractError("recovered OBIS result crosses project/source boundary")
                if result["coverage_state"] not in {"COMPLETE", "PARTIAL"}:
                    raise AdapterContractError("recovered coverage state is invalid")
                for key, maximum in (("items_seen", source.budget.max_items), ("pages_seen", source.budget.max_pages)):
                    value = result[key]
                    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
                        raise AdapterContractError(f"recovered {key} is outside the configured budget")
                if result["pages_seen"] < 1:
                    raise AdapterContractError("recovered result must report at least one page")
                values = result["measurements"]
                if not isinstance(values, Mapping) or set(values) != set(source.expected_measurements):
                    raise AdapterContractError("recovered measurement set does not match the source")
                for kind, value in values.items():
                    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                        raise AdapterContractError(f"recovered measurement {kind} is invalid")
                if result["source_timestamp"] is not None and not isinstance(result["source_timestamp"], str):
                    raise AdapterContractError("recovered source_timestamp is invalid")
                if not isinstance(result["limitations"], (list, tuple)) or any(
                    not isinstance(item, str) or not item for item in result["limitations"]
                ):
                    raise AdapterContractError("recovered limitations are invalid")
                if result["evidence_ref"] is not None and not isinstance(result["evidence_ref"], str):
                    raise AdapterContractError("recovered evidence_ref is invalid")
                reconciliation_id = str(uuid.uuid4())
                self.store.append_operation_reconciliation(
                    reconciliation_id=reconciliation_id,
                    scan_id=intent["scan_id"],
                    source_id=source.source_id,
                    outcome="SUCCEEDED",
                    recorded_at=_now(),
                    result=dict(result),
                )
                projection = self.project_reconciled_measurements(source_id)
                projection_state = next(
                    (item["state"] for item in projection if item["reconciliation_id"] == reconciliation_id),
                    "PROJECTION_PENDING",
                )
                outcomes.append({"scan_id": intent["scan_id"], "state": "RECONCILED_SUCCEEDED",
                                 "measurement_projection": projection_state})
            except Exception as exc:
                from .obis_bridge import OBISV02OperationFailed
                if isinstance(exc, OBISV02OperationFailed):
                    self.store.append_operation_reconciliation(
                        reconciliation_id=str(uuid.uuid4()),
                        scan_id=intent["scan_id"],
                        source_id=source.source_id,
                        outcome="FAILED",
                        recorded_at=_now(),
                        result={"operation_state": exc.state, "failure_code": exc.failure_code},
                    )
                    outcomes.append({"scan_id": intent["scan_id"], "state": "RECONCILED_FAILED"})
                elif isinstance(exc, (TransportOutcomeUnknown, BudgetExceeded, AuthorizationRevoked)):
                    outcomes.append({"scan_id": intent["scan_id"], "state": "UNRESOLVED",
                                     "reason_code": "status_outcome_unknown"})
                    if isinstance(exc, (BudgetExceeded, AuthorizationRevoked)):
                        break
                else:
                    # A malformed response or changed identity must never
                    # resolve an intent. Keep the evidence available for review.
                    outcomes.append({"scan_id": intent["scan_id"], "state": "UNRESOLVED",
                                     "reason_code": "reconciliation_validation_failed"})
        return outcomes

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
            return self._record_without_adapter(
                source, actor_id, scan_id, started_at,
                decision.coverage_state or "NOT_AUTHORIZED",
                decision.reason_code or "authorization_denied",
            )

        adapter = self.adapters.get(source.adapter_id)
        if adapter is None:
            return self._record_without_adapter(
                source, actor_id, scan_id, started_at, "NOT_CONFIGURED", "adapter_not_registered"
            )
        if adapter.adapter_id != source.adapter_id or adapter.version != source.adapter_version:
            return self._record_without_adapter(
                source, actor_id, scan_id, started_at, "FAILED", "adapter_version_mismatch"
            )

        # A subsequent run after process restart must settle old durable
        # operations before dispatching any new operation for this source.
        if self.store.list_unresolved_operation_intents(source_id):
            self.reconcile_pending(source_id, actor_id)
            if self.store.list_unresolved_operation_intents(source_id):
                raise ScanError(
                    "source has unresolved remote operations; no new operation was dispatched"
                )

        def still_authorized() -> bool:
            return self.gate.evaluate(self.registry, source, actor_id).allowed

        guard = BudgetGuard(source.budget, before_page=still_authorized)
        context = ScanContext(
            self.registry.project_id, actor_id, source, source.budget, guard,
            checkpoint, scan_id=scan_id,
        )
        operation_intent = None
        result: AdapterResult | None = None
        measurements: list[dict[str, Any]] = []
        failure_state: str | None = None
        failure_reason: str | None = None
        try:
            adapter.validate_config(source)
            prepare_operation = getattr(adapter, "prepare_operation", None)
            if getattr(adapter, "supports_durable_operations", False) and callable(prepare_operation):
                intent_fields = prepare_operation(context)
                operation_intent = self.store.create_operation_intent(
                    scan_id=scan_id,
                    created_at=started_at,
                    **intent_fields,
                )
                context = ScanContext(
                    self.registry.project_id, actor_id, source, source.budget, guard,
                    checkpoint, scan_id=scan_id, operation_intent=operation_intent,
                )
            result = adapter.scan(context)
            # Enforce the absolute deadline even when an adapter reports zero
            # items and therefore never calls consume_item() after its I/O.
            guard.check_deadline()
            if not isinstance(result, AdapterResult):
                raise AdapterContractError("adapter must return AdapterResult")
            if result.coverage_state not in {"COMPLETE", "PARTIAL", "FAILED"}:
                raise AdapterContractError("invalid adapter coverage state")
            for name, value, maximum in (
                ("items_seen", result.items_seen, source.budget.max_items),
                ("pages_seen", result.pages_seen, source.budget.max_pages),
            ):
                if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
                    raise AdapterContractError(f"{name} is outside the configured budget")
            if result.items_seen != guard.items_seen or result.pages_seen != guard.pages_seen:
                raise AdapterContractError("adapter counters do not match budget guard")
            if not isinstance(result.measurements, (list, tuple)):
                raise AdapterContractError("measurements must be a list or tuple")
            if len(result.measurements) > len(source.expected_measurements):
                raise AdapterContractError("measurement count exceeds declared measurement kinds")
            measurement_kinds = [
                item.get("kind") for item in result.measurements
                if isinstance(item, Mapping)
            ]
            if len(measurement_kinds) != len(result.measurements) or len(set(measurement_kinds)) != len(measurement_kinds):
                raise AdapterContractError("measurement kinds must be present and unique within a scan")
            if result.coverage_state == "FAILED" and result.measurements:
                raise AdapterContractError("failed scan cannot publish measurements")
            if result.reason_code is not None and (not isinstance(result.reason_code, str) or not result.reason_code):
                raise AdapterContractError("reason_code must be null or a non-empty string")
            if (
                not isinstance(result.limitations, (list, tuple))
                or any(not isinstance(item, str) or not item for item in result.limitations)
            ):
                raise AdapterContractError("limitations must be non-empty strings")
            measurements = [
                _validate_measurement(item, self.registry, source, adapter, result.coverage_state)
                for item in result.measurements
            ]
            if len({item["measurement_id"] for item in measurements}) != len(measurements):
                raise AdapterContractError("measurement IDs must be unique within a scan")
            if result.checkpoint is not None and not isinstance(result.checkpoint, Mapping):
                raise AdapterContractError("checkpoint must be an object")
        except AuthorizationRevoked:
            failure_state, failure_reason = "NOT_AUTHORIZED", "authorization_revoked"
        except TransportOutcomeUnknown:
            failure_state, failure_reason = "INDETERMINATE", "transport_outcome_unknown"
            if operation_intent is not None:
                self.store.transition_operation_intent(
                    scan_id, "INDETERMINATE", _now()
                )
        except BudgetExceeded:
            failure_state, failure_reason = "FAILED", "budget_exhausted"
        except AdapterContractError:
            failure_state, failure_reason = "FAILED", "adapter_contract_violation"
        except Exception:
            failure_state, failure_reason = "FAILED", "adapter_execution_failed"

        if failure_state is not None:
            failed_record = self._coverage(
                source, actor_id, scan_id, started_at, failure_state, failure_reason,
                adapter.adapter_id, adapter.version, guard.items_seen, guard.pages_seen,
                ["No complete measurement set was committed for this scan attempt."],
            )
            self.store.append_scan(failed_record, [])
            return ScanOutcome(
                scan_id, self.registry.project_id, source.source_id,
                failure_state, failure_reason, 0
            )

        if result is None:
            raise ScanError("adapter completed without a result")
        checkpoint_ref = scan_id if result.checkpoint is not None else None
        coverage_record = self._coverage(
            source, actor_id, scan_id, started_at, result.coverage_state, result.reason_code,
            adapter.adapter_id, adapter.version, result.items_seen, result.pages_seen,
            result.limitations, checkpoint_ref,
        )
        self.store.append_scan(
            coverage_record,
            measurements,
            checkpoint=result.checkpoint,
            checkpoint_updated_at=coverage_record["finished_at"] if result.checkpoint is not None else None,
            reconcile_operation_intent=operation_intent is not None,
        )
        return ScanOutcome(
            scan_id, self.registry.project_id, source.source_id,
            result.coverage_state, result.reason_code, len(measurements)
        )
