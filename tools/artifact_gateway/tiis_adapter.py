"""Read-only TIIS adapter for project-scoped Artifact Gateway receipts.

This adapter exposes receipt metadata only. It never returns extracted document
text, ZIP member listings, credentials, or the underlying artifact bytes.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from tradix.tiis import TIISValidator


INTERFACE_ID = "artifact.receipt"
INTERFACE_VERSION = "0.1.0"
_ARTIFACT_ID = re.compile(r"^[0-9a-f]{32}$")
_PROJECT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
_MAX_RECEIPT_BYTES = 1_048_576


class ArtifactReceiptTIISAdapterError(ValueError):
    """Raised when an artifact receipt request is malformed."""


def _timestamp(now: datetime | None) -> str:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now_must_be_timezone_aware")
    return current.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _validate_receipt(receipt: Mapping[str, Any], artifact_id: str, project_id: str) -> bool:
    if receipt.get("artifact_id") != artifact_id or receipt.get("project_id") != project_id:
        return False
    filename = receipt.get("filename")
    size_bytes = receipt.get("size_bytes")
    digest = receipt.get("sha256")
    backend = receipt.get("storage_backend")
    storage_ref = receipt.get("storage_ref")
    uploaded_at = receipt.get("uploaded_at")
    if not isinstance(filename, str) or not filename or len(filename) > 120:
        return False
    if type(size_bytes) is not int or size_bytes < 0:
        return False
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        return False
    if backend not in {"local", "s3", "github"}:
        return False
    if not isinstance(storage_ref, str) or not storage_ref or len(storage_ref) > 2048:
        return False
    if not isinstance(uploaded_at, str) or len(uploaded_at) > 64:
        return False
    try:
        parsed = datetime.fromisoformat(uploaded_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _safe_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    extraction = receipt.get("extraction")
    summary: dict[str, Any] = {}
    if isinstance(extraction, Mapping):
        for key in ("kind", "valid", "entry_count", "uncompressed_bytes", "encoding", "reason"):
            if key in extraction and isinstance(extraction[key], (str, int, bool)):
                summary[key] = extraction[key]
    fields = (
        "artifact_id",
        "project_id",
        "filename",
        "size_bytes",
        "sha256",
        "storage_backend",
        "storage_ref",
        "remote_commit_sha",
        "uploaded_at",
    )
    result = {key: receipt.get(key) for key in fields if key in receipt}
    result["extraction_summary"] = summary
    return result


class ArtifactReceiptTIISAdapter:
    """Serve one project's receipt metadata through a TIIS request boundary."""

    def __init__(
        self,
        *,
        project_id: str,
        root: str | Path,
        validator: TIISValidator,
        component_identity: Mapping[str, Any],
    ) -> None:
        if not isinstance(project_id, str) or not _PROJECT_ID.fullmatch(project_id):
            raise ValueError("project_id_invalid")
        root_path = Path(root)
        if not root_path.is_absolute():
            raise ValueError("artifact_root_must_be_absolute")
        self._project_id = project_id
        self._project_root = (root_path / project_id).resolve()
        self._receipts_root = self._project_root / "receipts"
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
            raise ArtifactReceiptTIISAdapterError("receipt_adapter_accepts_requests_only")
        if checked["interface_id"] != INTERFACE_ID:
            raise ArtifactReceiptTIISAdapterError("unexpected_interface")
        if checked["interface_version"] != INTERFACE_VERSION:
            raise ArtifactReceiptTIISAdapterError("unsupported_interface_version")
        if checked["operation"] != "read":
            return self._response(
                checked,
                outcome="rejected",
                payload={},
                error={
                    "code": "artifact.operation-unsupported",
                    "message": "Only receipt metadata reads are supported.",
                    "retryable": False,
                },
                now=now,
            )

        payload = checked["payload"]
        if set(payload) != {"artifact_id"} or not isinstance(payload.get("artifact_id"), str):
            return self._response(
                checked,
                outcome="rejected",
                payload={},
                error={
                    "code": "artifact.request-invalid",
                    "message": "The receipt request has an invalid payload.",
                    "retryable": False,
                },
                now=now,
            )
        artifact_id = payload["artifact_id"]
        if not _ARTIFACT_ID.fullmatch(artifact_id):
            return self._response(
                checked,
                outcome="failed",
                payload={},
                error={
                    "code": "artifact.not-found",
                    "message": "The requested receipt does not exist.",
                    "retryable": False,
                },
                now=now,
            )

        receipt_path = self._receipts_root / f"{artifact_id}.json"
        try:
            if receipt_path.is_symlink() or receipt_path.resolve().parent != self._receipts_root.resolve():
                raise FileNotFoundError
            if not receipt_path.is_file() or receipt_path.stat().st_size > _MAX_RECEIPT_BYTES:
                raise FileNotFoundError
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            if not isinstance(receipt, Mapping) or not _validate_receipt(receipt, artifact_id, self._project_id):
                raise FileNotFoundError
        except (OSError, ValueError, json.JSONDecodeError):
            return self._response(
                checked,
                outcome="failed",
                payload={},
                error={
                    "code": "artifact.not-found",
                    "message": "The requested receipt does not exist or is invalid.",
                    "retryable": False,
                },
                now=now,
            )

        return self._response(
            checked,
            outcome="succeeded",
            payload={"receipt": _safe_receipt(receipt)},
            now=now,
        )

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
