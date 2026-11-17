"""Strict import boundary for normalized, permission-backed direct-sales reports."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re

from .catalog import SourceDescriptor
from .demand import DemandObservation, DIRECT_SALES_METRICS

_MARKET_CODE = re.compile(r"^[A-Z]{2}$")
_MAX_PAYLOAD_BYTES = 10_000_000
_MAX_RECORDS = 10_000
_ROOT_KEYS = {
    "schema_version", "report_id", "source_id", "permission_reference",
    "market_code", "generated_at", "period_start", "period_end",
    "coverage_complete", "records",
}
_RECORD_KEYS = {"record_id", "product_identity_key", "metric", "value", "unit"}


@dataclass(frozen=True, slots=True)
class SalesReportImport:
    report_id: str
    source_id: str
    market_code: str
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    coverage_complete: bool
    raw_payload_sha256: str
    observations: tuple[DemandObservation, ...]


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_json_number(value: str) -> object:
    raise ValueError(f"JSON floating-point values are not accepted: {value}")


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"non-finite JSON value is not accepted: {value}")


def _timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} is not a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def import_normalized_sales_report(
    payload: bytes,
    descriptor: SourceDescriptor,
) -> SalesReportImport:
    """Parse a strict JSON sales report and bind every record to its approved source."""

    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")
    if not payload or len(payload) > _MAX_PAYLOAD_BYTES:
        raise ValueError("payload must be between 1 byte and 10 MB")
    if descriptor.permission_status != "approved":
        raise ValueError("sales report source is not approved")
    if not descriptor.permission_reference or not descriptor.permission_reference.strip():
        raise ValueError("approved sales source requires a permission reference")

    try:
        document = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_float=_reject_json_number,
            parse_constant=_reject_json_constant,
        )
    except UnicodeDecodeError as exc:
        raise ValueError("sales report must be UTF-8 JSON") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("sales report is not valid JSON") from exc

    if not isinstance(document, dict) or set(document) != _ROOT_KEYS:
        raise ValueError("sales report root keys do not match schema version 1")
    if document["schema_version"] != "1":
        raise ValueError("unsupported sales report schema_version")
    for field in ("report_id", "source_id", "permission_reference", "market_code"):
        if not isinstance(document[field], str) or not document[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if document["source_id"] != descriptor.source_id:
        raise ValueError("report source_id does not match the approved source")
    if document["permission_reference"] != descriptor.permission_reference:
        raise ValueError("report permission_reference does not match the approved source")
    market_code = document["market_code"]
    if not _MARKET_CODE.fullmatch(market_code):
        raise ValueError("market_code must be an uppercase two-letter code")

    generated_at = _timestamp(document["generated_at"], "generated_at")
    period_start = _timestamp(document["period_start"], "period_start")
    period_end = _timestamp(document["period_end"], "period_end")
    if period_start >= period_end:
        raise ValueError("period_start must be before period_end")
    if period_end > generated_at:
        raise ValueError("period_end cannot be after generated_at")
    coverage_complete = document["coverage_complete"]
    if not isinstance(coverage_complete, bool):
        raise TypeError("coverage_complete must be a boolean")

    records = document["records"]
    if not isinstance(records, list) or len(records) > _MAX_RECORDS:
        raise ValueError("records must be an array with at most 10000 entries")

    payload_hash = hashlib.sha256(payload).hexdigest()
    seen_ids: set[str] = set()
    observations: list[DemandObservation] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict) or set(record) != _RECORD_KEYS:
            raise ValueError(f"record {index} keys do not match schema version 1")
        record_id = record["record_id"]
        product_key = record["product_identity_key"]
        metric = record["metric"]
        unit = record["unit"]
        value_text = record["value"]
        if not isinstance(record_id, str) or not record_id.strip():
            raise ValueError(f"record {index} record_id must be a non-empty string")
        if record_id in seen_ids:
            raise ValueError(f"duplicate sales record_id: {record_id}")
        seen_ids.add(record_id)
        if not isinstance(product_key, str) or not product_key.strip():
            raise ValueError(f"record {index} product_identity_key must be a non-empty string")
        if metric not in DIRECT_SALES_METRICS:
            raise ValueError(f"record {index} metric must be transaction_count or units_sold")
        expected_unit = "transactions" if metric == "transaction_count" else "units"
        if unit != expected_unit:
            raise ValueError(f"record {index} unit must be {expected_unit}")
        if not isinstance(value_text, str):
            raise TypeError(f"record {index} value must be a decimal string")
        try:
            value = Decimal(value_text)
        except InvalidOperation as exc:
            raise ValueError(f"record {index} value is not a valid decimal") from exc
        if not value.is_finite() or value < 0:
            raise ValueError(f"record {index} value must be finite and non-negative")

        observations.append(DemandObservation(
            product_identity_key=product_key,
            source_id=descriptor.source_id,
            source_record_id=f"{document['report_id']}:{record_id}",
            market_code=market_code,
            metric=metric,
            value=value,
            unit=unit,
            observed_at=generated_at,
            window_start=period_start,
            window_end=period_end,
            verified=coverage_complete,
            reference=f"sales-report://{descriptor.source_id}/{document['report_id']}/{record_id}",
            permission_reference=descriptor.permission_reference,
            raw_payload_sha256=payload_hash,
            coverage_complete=coverage_complete,
        ))

    observations.sort(key=lambda item: (item.product_identity_key, item.metric, item.source_record_id))
    return SalesReportImport(
        report_id=document["report_id"],
        source_id=descriptor.source_id,
        market_code=market_code,
        generated_at=generated_at,
        period_start=period_start,
        period_end=period_end,
        coverage_complete=coverage_complete,
        raw_payload_sha256=payload_hash,
        observations=tuple(observations),
    )
