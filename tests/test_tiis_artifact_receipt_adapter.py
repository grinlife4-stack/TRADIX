import json
from datetime import datetime, timezone
from uuid import uuid4

from tradix.tiis import TIISValidator
from tools.artifact_gateway.tiis_adapter import ArtifactReceiptTIISAdapter


NOW = datetime(2026, 11, 20, 12, 0, 10, tzinfo=timezone.utc)
SENDER = {"project_id": "tradix", "component_id": "factory-runtime"}
GATEWAY = {"project_id": "tradix", "component_id": "artifact-gateway"}
ARTIFACT_ID = "a" * 32


def request(artifact_id=ARTIFACT_ID):
    return {
        "protocol": "TIIS",
        "protocol_version": "0.1",
        "message_type": "request",
        "message_id": str(uuid4()),
        "correlation_id": str(uuid4()),
        "sender": SENDER,
        "recipient": GATEWAY,
        "interface_id": "artifact.receipt",
        "interface_version": "0.1.0",
        "operation": "read",
        "issued_at": "2026-11-20T12:00:00Z",
        "expires_at": "2026-11-20T12:01:00Z",
        "idempotency_key": "artifact-read-key-0001",
        "payload": {"artifact_id": artifact_id},
    }


def test_receipt_adapter_returns_only_safe_project_scoped_metadata(tmp_path):
    receipts = tmp_path / "nexora" / "receipts"
    receipts.mkdir(parents=True)
    receipt = {
        "artifact_id": ARTIFACT_ID,
        "project_id": "nexora",
        "filename": "report.txt",
        "size_bytes": 24,
        "sha256": "b" * 64,
        "storage_backend": "local",
        "storage_ref": "objects/bb/example",
        "remote_commit_sha": None,
        "uploaded_at": "2026-11-20T12:00:00Z",
        "extraction": {
            "kind": "text",
            "encoding": "utf-8",
            "text": "private extracted text",
            "entries": ["private/path"],
        },
    }
    (receipts / f"{ARTIFACT_ID}.json").write_text(json.dumps(receipt), encoding="utf-8")
    adapter = ArtifactReceiptTIISAdapter(
        project_id="nexora",
        root=tmp_path,
        validator=TIISValidator(authorization_policy=lambda *_args: True),
        component_identity=GATEWAY,
    )
    response = adapter.handle(request(), authenticated_sender=SENDER, now=NOW)
    safe = response["payload"]["receipt"]
    assert response["outcome"] == "succeeded"
    assert safe["artifact_id"] == ARTIFACT_ID
    assert safe["extraction_summary"]["kind"] == "text"
    assert "text" not in safe["extraction_summary"]
    assert "entries" not in safe["extraction_summary"]


def test_receipt_adapter_rejects_cross_project_receipt(tmp_path):
    receipts = tmp_path / "nexora" / "receipts"
    receipts.mkdir(parents=True)
    receipt = {"artifact_id": ARTIFACT_ID, "project_id": "other-project"}
    (receipts / f"{ARTIFACT_ID}.json").write_text(json.dumps(receipt), encoding="utf-8")
    adapter = ArtifactReceiptTIISAdapter(
        project_id="nexora",
        root=tmp_path,
        validator=TIISValidator(authorization_policy=lambda *_args: True),
        component_identity=GATEWAY,
    )
    response = adapter.handle(request(), authenticated_sender=SENDER, now=NOW)
    assert response["outcome"] == "failed"
    assert response["error"]["code"] == "artifact.not-found"


def test_receipt_adapter_rejects_corrupt_receipt_metadata(tmp_path):
    receipts = tmp_path / "nexora" / "receipts"
    receipts.mkdir(parents=True)
    receipt = {
        "artifact_id": ARTIFACT_ID,
        "project_id": "nexora",
        "filename": "report.txt",
        "size_bytes": 24,
        "sha256": "not-a-sha256",
        "storage_backend": "local",
        "storage_ref": "objects/report",
        "uploaded_at": "2026-11-20T12:00:00Z",
    }
    (receipts / f"{ARTIFACT_ID}.json").write_text(json.dumps(receipt), encoding="utf-8")
    adapter = ArtifactReceiptTIISAdapter(
        project_id="nexora",
        root=tmp_path,
        validator=TIISValidator(authorization_policy=lambda *_args: True),
        component_identity=GATEWAY,
    )
    response = adapter.handle(request(), authenticated_sender=SENDER, now=NOW)
    assert response["outcome"] == "failed"
    assert response["error"]["code"] == "artifact.not-found"


def test_receipt_adapter_rejects_path_shaped_artifact_ids(tmp_path):
    adapter = ArtifactReceiptTIISAdapter(
        project_id="nexora",
        root=tmp_path,
        validator=TIISValidator(authorization_policy=lambda *_args: True),
        component_identity=GATEWAY,
    )
    response = adapter.handle(request("../outside"), authenticated_sender=SENDER, now=NOW)
    assert response["outcome"] == "failed"
    assert response["error"]["code"] == "artifact.not-found"


def test_receipt_adapter_requires_authorized_tiis_identity(tmp_path):
    adapter = ArtifactReceiptTIISAdapter(
        project_id="nexora",
        root=tmp_path,
        validator=TIISValidator(),
        component_identity=GATEWAY,
    )
    import pytest
    from tradix.tiis import TIISAuthorizationError
    with pytest.raises(TIISAuthorizationError, match="authorization_policy_not_configured"):
        adapter.handle(request(), authenticated_sender=SENDER, now=NOW)
