from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from tradix.tiis import TIISAuthorizationError, TIISValidationError, TIISValidator
from tradix.tools import ToolCatalog, ToolCatalogTIISAdapter, ToolDescriptor


NOW = datetime(2026, 11, 20, 12, 0, 10, tzinfo=timezone.utc)
CLIENT = {"project_id": "tradix", "component_id": "factory-runtime"}
CATALOG = {"project_id": "tradix", "component_id": "tool-catalog"}
SCHEMA_PATH = Path(__file__).parents[1] / "standards" / "tiis" / "0.1" / "message.schema.json"


def descriptor(tool_id: str = "sample.reader") -> ToolDescriptor:
    return ToolDescriptor(
        tool_id=tool_id,
        version="1.2.0",
        category="image" if tool_id == "sample.image" else "document",
        source_uri="https://github.com/example/sample-reader",
        license_id="MIT",
        platforms=("linux", "windows"),
        capabilities=("document.read",),
        execution_modes=("local",),
        adapter_contract_version="0.1.0",
        free_open_source=True,
    )


def make_request(operation: str, payload: dict) -> dict:
    return {
        "protocol": "TIIS",
        "protocol_version": "0.1",
        "message_type": "request",
        "message_id": str(uuid4()),
        "correlation_id": str(uuid4()),
        "sender": dict(CLIENT),
        "recipient": dict(CATALOG),
        "interface_id": "tool.catalog",
        "interface_version": "1.0.0",
        "operation": operation,
        "issued_at": "2026-11-20T12:00:00Z",
        "expires_at": "2026-11-20T12:01:00Z",
        "payload": payload,
    }


def policy(sender, recipient, interface_id, action, message_type):
    return (
        dict(sender) == CLIENT
        and dict(recipient) == CATALOG
        and interface_id == "tool.catalog"
        and message_type == "request"
        and action in {"tool.get", "tool.list", "tool.delete"}
    )


@pytest.fixture
def adapter(tmp_path):
    catalog = ToolCatalog(tmp_path / "catalog.sqlite3")
    catalog.register(descriptor(), actor="test-fixture", reason="seed metadata")
    validator = TIISValidator(authorization_policy=policy)
    return ToolCatalogTIISAdapter(catalog, validator, CATALOG)


def assert_valid_response(response: dict) -> None:
    schema = __import__("json").loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(response)


def test_tool_get_uses_tiis_and_returns_schema_valid_response(adapter) -> None:
    request = make_request("tool.get", {"tool_id": "sample.reader", "version": "1.2.0"})
    response = adapter.handle(request, authenticated_sender=CLIENT, now=NOW)

    assert_valid_response(response)
    assert response["message_type"] == "response"
    assert response["outcome"] == "succeeded"
    assert response["in_reply_to"] == request["message_id"]
    assert response["correlation_id"] == request["correlation_id"]
    assert response["sender"] == CATALOG
    assert response["recipient"] == CLIENT
    assert response["payload"]["tool"]["tool_id"] == "sample.reader"
    assert response["payload"]["tool"]["platforms"] == ["linux", "windows"]


def test_tool_list_is_read_only_and_supports_bounded_filters(adapter) -> None:
    adapter._catalog.register(
        descriptor("sample.image"),
        actor="test-fixture",
        reason="seed second metadata record",
    )
    request = make_request("tool.list", {"category": "document"})
    response = adapter.handle(request, authenticated_sender=CLIENT, now=NOW)

    assert_valid_response(response)
    assert response["outcome"] == "succeeded"
    assert [item["tool_id"] for item in response["payload"]["tools"]] == ["sample.reader"]


def test_missing_tool_returns_normalized_rejection(adapter) -> None:
    request = make_request("tool.get", {"tool_id": "missing.tool", "version": "1.0.0"})
    response = adapter.handle(request, authenticated_sender=CLIENT, now=NOW)

    assert_valid_response(response)
    assert response["outcome"] == "rejected"
    assert response["error"]["code"] == "tool.not-found"
    assert response["error"]["retryable"] is False


def test_unsupported_operation_is_rejected_without_catalog_mutation(adapter) -> None:
    request = make_request("tool.delete", {"tool_id": "sample.reader"})
    response = adapter.handle(request, authenticated_sender=CLIENT, now=NOW)

    assert_valid_response(response)
    assert response["outcome"] == "rejected"
    assert response["error"]["code"] == "operation.unsupported"
    assert adapter._catalog.get("sample.reader", "1.2.0")["status"] == "discovered"


def test_claimed_sender_cannot_override_authenticated_identity(adapter) -> None:
    request = make_request("tool.list", {})
    with pytest.raises(TIISAuthorizationError, match="authenticated_sender_mismatch"):
        adapter.handle(
            request,
            authenticated_sender={"project_id": "tradix", "component_id": "untrusted"},
            now=NOW,
        )


def test_wrong_recipient_is_rejected(adapter) -> None:
    request = make_request("tool.list", {})
    request["recipient"] = {"project_id": "tradix", "component_id": "artifact-gateway"}
    with pytest.raises(TIISAuthorizationError, match="recipient_mismatch"):
        adapter.handle(request, authenticated_sender=CLIENT, now=NOW)


def test_unapproved_operation_scope_is_denied_before_catalog_access(tmp_path) -> None:
    catalog = ToolCatalog(tmp_path / "catalog.sqlite3")
    validator = TIISValidator(authorization_policy=lambda *_args: False)
    adapter = ToolCatalogTIISAdapter(catalog, validator, CATALOG)
    request = make_request("tool.list", {})
    with pytest.raises(TIISAuthorizationError, match="operation_not_authorized"):
        adapter.handle(request, authenticated_sender=CLIENT, now=NOW)


def test_tool_get_rejects_extra_payload_fields(adapter) -> None:
    request = make_request("tool.get", {"tool_id": "sample.reader", "version": "1.2.0", "project_id": "nexora"})
    with pytest.raises(TIISValidationError, match="tool_get_payload_fields_invalid"):
        adapter.handle(request, authenticated_sender=CLIENT, now=NOW)
