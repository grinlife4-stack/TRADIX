import time

import pytest

from ecoscan.contracts import AdapterContractError, BudgetExceeded, TransportOutcomeUnknown
from ecoscan.obis_bridge import OBISV02Invoker, OBISV02OperationFailed


REQUIRED = "ecoscan:inventory:read"
EXTRA = "admin:write"


class FakeV02Client:
    instances = []
    default_state = "SUCCEEDED"
    default_failure_code = None

    def __init__(
        self, *, local_peer_id, remote_peer_id, key_id, principal_ref,
        secret, scopes, timeout,
    ):
        self.local_peer_id = local_peer_id
        self.remote_peer_id = remote_peer_id
        self.key_id = key_id
        self.principal_ref = principal_ref
        self.secret = secret
        self.scopes = set(scopes)
        self.timeout = timeout
        self.response = {
            "sender": {"peer_id": remote_peer_id},
            "recipient": {"peer_id": local_peer_id},
            "operation": {
                "operation_id": "operation-001",
                "request_hash": "a" * 64,
                "state": self.default_state,
                "result": {"items_seen": 1},
                "result_ref": None,
                "failure_code": self.default_failure_code,
            },
        }
        self.calls = []
        self.instances.append(self)

    def invoke(self, endpoint, capability_id, capability_version, payload, **kwargs):
        self.calls.append((endpoint, capability_id, capability_version, payload, kwargs))
        return self.response

    def status(self, endpoint, capability_id, capability_version, operation_id, **kwargs):
        self.calls.append((endpoint, capability_id, capability_version, operation_id, kwargs))
        return self.response


def make_invoker():
    FakeV02Client.instances.clear()
    FakeV02Client.default_state = "SUCCEEDED"
    FakeV02Client.default_failure_code = None
    original = FakeV02Client(
        local_peer_id="peer:ecoscan",
        remote_peer_id="peer:owner",
        key_id="ecoscan-key",
        principal_ref="principal:ecoscan",
        secret=b"0123456789abcdef0123456789abcdef",
        scopes={REQUIRED, EXTRA},
        timeout=4.0,
    )
    return OBISV02Invoker(original), original


def test_v02_invoker_narrows_scopes_and_returns_only_committed_result():
    invoker, original = make_invoker()
    response = invoker.invoke(
        "http://127.0.0.1:9000", "ecoscan.inventory.read", "1.0",
        {"project_id": "project-a", "source_id": "source-a"},
            operation_id="operation-001",
            idempotency_key="idem-001",
    )

    used_client = FakeV02Client.instances[-1]
    assert used_client is not original
    assert used_client.scopes == {REQUIRED}
    assert response["outcome"] == "succeeded"
    assert response["result"] == {"items_seen": 1}
    assert used_client.calls[0][4]["operation_id"] == "operation-001"
    assert used_client.calls[0][4]["idempotency_key"] == "idem-001"
    assert used_client.calls[0][4]["operation_ttl"] == 300


def test_v02_invoker_never_converts_unknown_operation_into_success():
    invoker, _ = make_invoker()
    FakeV02Client.default_state = "UNKNOWN"
    with pytest.raises(TransportOutcomeUnknown):
        invoker.invoke(
            "http://127.0.0.1:9000", "ecoscan.inventory.read", "1.0",
            {"project_id": "project-a", "source_id": "source-a"},
            operation_id="operation-001",
            idempotency_key="idem-001",
            scopes={REQUIRED},
        )


def test_v02_invoker_surfaces_known_terminal_failure():
    invoker, _ = make_invoker()
    FakeV02Client.default_state = "FAILED"
    FakeV02Client.default_failure_code = "provider.denied"
    with pytest.raises(OBISV02OperationFailed) as raised:
        invoker.invoke(
            "http://127.0.0.1:9000", "ecoscan.inventory.read", "1.0",
            {"project_id": "project-a", "source_id": "source-a"},
            operation_id="operation-001",
            idempotency_key="idem-001",
            scopes={REQUIRED},
        )
    assert raised.value.failure_code == "provider.denied"


def test_v02_invoker_rejects_scope_escalation_and_expired_deadline():
    invoker, original = make_invoker()
    with pytest.raises(AdapterContractError):
        invoker.invoke(
            "http://127.0.0.1:9000", "ecoscan.inventory.read", "1.0",
            {"project_id": "project-a", "source_id": "source-a"},
            operation_id="operation-001",
            idempotency_key="idem-001",
            scopes={REQUIRED, "billing:write"},
        )
    with pytest.raises(BudgetExceeded):
        invoker.invoke(
            "http://127.0.0.1:9000", "ecoscan.inventory.read", "1.0",
            {"project_id": "project-a", "source_id": "source-a"},
            operation_id="operation-001",
            idempotency_key="idem-001",
            scopes={REQUIRED}, deadline=time.monotonic() - 1,
        )
    assert original.calls == []


def test_v02_invoker_requires_operation_ttl_longer_than_message_ttl():
    _, original = make_invoker()
    with pytest.raises(ValueError):
        OBISV02Invoker(original, operation_ttl=60)


def test_v02_invoker_status_is_identity_scoped_and_checks_durable_request_hash():
    invoker, original = make_invoker()
    response = invoker.status(
        "http://127.0.0.1:9000",
        "ecoscan.inventory.read",
        "1.0",
        "operation-001",
        resource={"project_id": "project-a", "source_id": "source-a"},
        expected_request_hash="a" * 64,
        scopes={REQUIRED},
    )
    used_client = FakeV02Client.instances[-1]
    assert used_client is not original
    assert used_client.scopes == {REQUIRED}
    assert response["outcome"] == "succeeded"
    assert response["operation"]["operation_id"] == "operation-001"
    assert used_client.calls[0][3] == "operation-001"
    assert used_client.calls[0][4]["resource"] == {
        "project_id": "project-a", "source_id": "source-a"
    }

    with pytest.raises(AdapterContractError, match="request hash"):
        invoker.status(
            "http://127.0.0.1:9000",
            "ecoscan.inventory.read",
            "1.0",
            "operation-001",
            resource={"project_id": "project-a", "source_id": "source-a"},
            expected_request_hash="b" * 64,
            scopes={REQUIRED},
        )
