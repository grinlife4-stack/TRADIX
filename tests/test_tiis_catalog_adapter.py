from datetime import datetime, timezone
from uuid import uuid4

import pytest

from tradix.tiis import TIISAuthorizationError, TIISValidator
from tradix.tools.catalog import ToolCatalog, ToolDescriptor
from tradix.tools.tiis_catalog import ToolCatalogTIISAdapter


NOW = datetime(2026, 11, 20, 12, 0, 10, tzinfo=timezone.utc)
SENDER = {"project_id": "tradix", "component_id": "tool-admin"}
CATALOG = {"project_id": "tradix", "component_id": "tool-catalog"}


def request(operation, payload):
    return {
        "protocol": "TIIS",
        "protocol_version": "0.1",
        "message_type": "request",
        "message_id": str(uuid4()),
        "correlation_id": str(uuid4()),
        "sender": SENDER,
        "recipient": CATALOG,
        "interface_id": "tool.catalog",
        "interface_version": "0.1.0",
        "operation": operation,
        "issued_at": "2026-11-20T12:00:00Z",
        "expires_at": "2026-11-20T12:01:00Z",
        "idempotency_key": "catalog-request-key-0001",
        "payload": payload,
    }


def adapter(tmp_path, policy=None):
    catalog = ToolCatalog(tmp_path / "catalog.sqlite")
    validator = TIISValidator(authorization_policy=policy or (lambda *_args: True))
    return catalog, ToolCatalogTIISAdapter(catalog, validator, CATALOG)


def descriptor():
    return ToolDescriptor(
        tool_id="pdf-reader",
        version="1.0.0",
        category="document",
        source_uri="https://example.org/pdf-reader",
        license_id="Apache-2.0",
        platforms=("linux",),
        capabilities=("pdf.read",),
        execution_modes=("bounded",),
        adapter_contract_version="0.1.0",
        free_open_source=True,
        notes="Metadata-only test fixture",
    )


def test_catalog_read_operations_are_exposed_through_tiis(tmp_path):
    catalog, service = adapter(tmp_path)
    catalog.register(descriptor(), actor="bootstrap")
    response = service.handle(
        request("get", {"tool_id": "pdf-reader", "version": "1.0.0"}),
        authenticated_sender=SENDER,
        now=NOW,
    )
    assert response["outcome"] == "succeeded"
    assert response["payload"]["result"]["status"] == "discovered"

    listed = service.handle(request("list", {"status": "discovered"}), authenticated_sender=SENDER, now=NOW)
    assert len(listed["payload"]["result"]) == 1

    history = service.handle(
        request("history", {"tool_id": "pdf-reader", "version": "1.0.0"}),
        authenticated_sender=SENDER,
        now=NOW,
    )
    assert history["payload"]["result"][0]["status"] == "discovered"


def test_catalog_mutations_remain_disabled_until_durable_idempotency_exists(tmp_path):
    catalog, service = adapter(tmp_path)
    response = service.handle(
        request("register", {"descriptor": {"tool_id": "pdf-reader"}}),
        authenticated_sender=SENDER,
        now=NOW,
    )
    assert response["outcome"] == "rejected"
    assert response["error"]["code"] == "catalog.mutation-disabled"
    assert catalog.get("pdf-reader", "1.0.0") is None


def test_catalog_lifecycle_transition_is_not_exposed_yet(tmp_path):
    catalog, service = adapter(tmp_path)
    catalog.register(descriptor(), actor="bootstrap")
    response = service.handle(
        request("transition", {
            "tool_id": "pdf-reader",
            "version": "1.0.0",
            "status": "evaluated",
            "reason": "evidence reviewed",
            "evidence_ref": "evidence://review/pdf-reader",
        }),
        authenticated_sender=SENDER,
        now=NOW,
    )
    assert response["outcome"] == "rejected"
    assert response["error"]["code"] == "catalog.mutation-disabled"
    assert catalog.history("pdf-reader", "1.0.0")[-1]["status"] == "discovered"


def test_catalog_rejects_caller_supplied_actor_on_read_request(tmp_path):
    _, service = adapter(tmp_path)
    response = service.handle(
        request("get", {"tool_id": "pdf-reader", "version": "1.0.0", "actor": "root"}),
        authenticated_sender=SENDER,
        now=NOW,
    )
    assert response["outcome"] == "rejected"
    assert response["error"]["code"] == "catalog.request-invalid"


def test_catalog_requires_tiis_authorization_policy(tmp_path):
    catalog = ToolCatalog(tmp_path / "catalog.sqlite")
    service = ToolCatalogTIISAdapter(catalog, TIISValidator(), CATALOG)
    with pytest.raises(TIISAuthorizationError, match="authorization_policy_not_configured"):
        service.handle(
            request("list", {}),
            authenticated_sender=SENDER,
            now=NOW,
        )


def test_catalog_response_is_a_valid_correlated_tiis_response(tmp_path):
    _, service = adapter(tmp_path)
    req = request("list", {})
    response = service.handle(req, authenticated_sender=SENDER, now=NOW)
    validator = TIISValidator(authorization_policy=lambda *_args: True)
    validator.validate(
        response,
        authenticated_sender=CATALOG,
        expected_recipient=SENDER,
        now=NOW,
    )
    assert response["in_reply_to"] == req["message_id"]
    assert response["correlation_id"] == req["correlation_id"]
