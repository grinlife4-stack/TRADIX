"""Wire-level ECOSCAN integration against the independent BRIDEX OBIS peer.

The reference peer is checked out at a pinned review commit by the ECOSCAN
workflow and installed only in the test environment. It is never an ECOSCAN
runtime dependency.
"""
from __future__ import annotations

import time

import pytest

from obis_bridge import (
    Credential,
    OBISClient,
    OBISPeer,
    OBISRequestError,
    OBISServer,
    register_ecoscan_inventory_capability,
)

from ecoscan.contracts import BudgetExceeded, BudgetGuard, ScanContext
from ecoscan.models import RetentionPolicy, ScanBudget, SourceDescriptor
from ecoscan.obis_bridge import OBISBridgeAdapter, REQUIRED_SCOPE


SECRET = b"0123456789abcdef0123456789abcdef"
PROJECT_ID = "project-alpha"
SOURCE_ID = "source-storage"
OWNER_PEER_ID = "peer:source-owner"
ECOSCAN_PEER_ID = "peer:ecoscan"


def _source(source_id: str = SOURCE_ID, timeout_seconds: float = 5) -> SourceDescriptor:
    return SourceDescriptor(
        source_id=source_id,
        owner_id="project-alpha-owner",
        operator_id="project-alpha-operator",
        subsystem_id="storage",
        source_type="obis_bridge",
        locator=OWNER_PEER_ID,
        adapter_id="obis_bridge",
        adapter_version="0.1.0",
        enabled=True,
        scope_tags=("remote", "read-only"),
        budget=ScanBudget(
            max_pages=5,
            max_items=20,
            timeout_seconds=timeout_seconds,
            max_duration_seconds=timeout_seconds,
        ),
        expected_measurements=("logical_bytes", "file_count"),
        retention_policy=RetentionPolicy(history_days=30, evidence_days=0),
        created_at="2026-11-20T00:00:00Z",
        updated_at="2026-11-20T00:00:00Z",
    )


def _peer(allowed_resources: frozenset[tuple[str, str]], provider):
    credential = Credential(
        key_id="ecoscan-dev-key",
        peer_id=ECOSCAN_PEER_ID,
        principal_ref="principal:ecoscan",
        secret=SECRET,
        allowed_scopes=frozenset({REQUIRED_SCOPE}),
        allowed_resources=allowed_resources,
    )
    peer = OBISPeer(OWNER_PEER_ID, [credential])
    register_ecoscan_inventory_capability(peer, provider)
    return peer


def _client() -> OBISClient:
    return OBISClient(
        local_peer_id=ECOSCAN_PEER_ID,
        remote_peer_id=OWNER_PEER_ID,
        key_id="ecoscan-dev-key",
        principal_ref="principal:ecoscan",
        secret=SECRET,
        scopes={REQUIRED_SCOPE},
    )


def _context(source: SourceDescriptor) -> ScanContext:
    return ScanContext(
        project_id=PROJECT_ID,
        actor_id="ecoscan-test-operator",
        source=source,
        budget=source.budget,
        guard=BudgetGuard(source.budget),
    )


def test_ecoscan_adapter_exchanges_real_obis_http_messages_with_independent_peer():
    provider_calls = []

    def provider(project_id, source_id, measurement_kinds):
        provider_calls.append((project_id, source_id, measurement_kinds))
        return {
            "coverage_state": "COMPLETE",
            "items_seen": 2,
            "pages_seen": 1,
            "measurements": {"logical_bytes": 4096, "file_count": 2},
            "source_timestamp": "2026-11-20T10:00:00Z",
            "limitations": [],
            "evidence_ref": "test-evidence:inventory-001",
        }

    peer = _peer(frozenset({(PROJECT_ID, SOURCE_ID)}), provider)
    with OBISServer(peer) as server:
        adapter = OBISBridgeAdapter(_client(), server.address)
        source = _source()
        adapter.validate_config(source)
        result = adapter.scan(_context(source))

    assert provider_calls == [(PROJECT_ID, SOURCE_ID, ("logical_bytes", "file_count"))]
    assert result.coverage_state == "COMPLETE"
    assert result.items_seen == 2
    assert result.pages_seen == 1
    assert {item["kind"]: item["value"] for item in result.measurements} == {
        "logical_bytes": 4096,
        "file_count": 2,
    }
    assert all(item["project_id"] == PROJECT_ID for item in result.measurements)
    assert all(item["source_id"] == SOURCE_ID for item in result.measurements)
    assert all(item["adapter_id"] == "obis_bridge" for item in result.measurements)


def test_adapter_passes_deadline_and_rejects_late_empty_peer_response():
    class SlowEmptyClient:
        local_peer_id = ECOSCAN_PEER_ID
        remote_peer_id = OWNER_PEER_ID
        scopes = frozenset({REQUIRED_SCOPE})

        def __init__(self):
            self.deadline = None

        def invoke(
            self, endpoint, capability_id, capability_version, payload,
            scopes=None, deadline=None,
        ):
            self.deadline = deadline
            time.sleep(1.05)
            return {
                "sender": {"peer_id": OWNER_PEER_ID},
                "recipient": {"peer_id": ECOSCAN_PEER_ID},
                "outcome": "succeeded",
                "result": {
                    "project_id": PROJECT_ID,
                    "source_id": SOURCE_ID,
                    "coverage_state": "COMPLETE",
                    "items_seen": 0,
                    "pages_seen": 1,
                    "measurements": {"logical_bytes": 0, "file_count": 0},
                    "source_timestamp": None,
                    "limitations": [],
                    "evidence_ref": None,
                },
            }

    source = _source(timeout_seconds=1)
    context = _context(source)
    client = SlowEmptyClient()
    adapter = OBISBridgeAdapter(client, "http://127.0.0.1:8080")
    started = time.monotonic()

    with pytest.raises(BudgetExceeded):
        adapter.scan(context)

    assert client.deadline == context.guard.deadline
    assert time.monotonic() - started < 0.5


def test_independent_peer_denies_ungranted_project_source_before_provider_execution():
    provider_calls = []

    def provider(project_id, source_id, measurement_kinds):
        provider_calls.append((project_id, source_id, measurement_kinds))
        return {
            "coverage_state": "COMPLETE",
            "items_seen": 0,
            "pages_seen": 1,
            "measurements": {"logical_bytes": 0, "file_count": 0},
            "source_timestamp": None,
            "limitations": [],
            "evidence_ref": None,
        }

    peer = _peer(frozenset({(PROJECT_ID, "different-source")}), provider)
    source = _source()
    with OBISServer(peer) as server:
        adapter = OBISBridgeAdapter(_client(), server.address)
        adapter.validate_config(source)
        with pytest.raises(OBISRequestError) as raised:
            adapter.scan(_context(source))

    assert raised.value.code == "authorization.denied"
    assert provider_calls == []


def test_adapter_rejects_peer_identity_mismatch_before_wire_call():
    source = _source()
    wrong_client = OBISClient(
        local_peer_id=ECOSCAN_PEER_ID,
        remote_peer_id="peer:unexpected",
        key_id="ecoscan-dev-key",
        principal_ref="principal:ecoscan",
        secret=SECRET,
        scopes={REQUIRED_SCOPE},
    )
    adapter = OBISBridgeAdapter(wrong_client, "http://127.0.0.1:8080")
    with pytest.raises(ValueError):
        adapter.validate_config(source)
