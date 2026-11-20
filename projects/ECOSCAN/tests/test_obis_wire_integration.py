"""Wire-level ECOSCAN integration against the independent BRIDEX OBIS peer.

The reference peer is checked out at a pinned review commit by the ECOSCAN
workflow and installed only in the test environment. It is never an ECOSCAN
runtime dependency.
"""
from __future__ import annotations

import os
import subprocess
import os
import subprocess
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

from ecoscan.contracts import BudgetExceeded, BudgetGuard, ScanContext, TransportOutcomeUnknown
from ecoscan.models import RetentionPolicy, ScanBudget, SourceDescriptor
from ecoscan.obis_bridge import OBISBridgeAdapter, OBISV02Invoker, REQUIRED_SCOPE


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
    assert time.monotonic() - started >= 1.0


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


def test_adapter_classifies_peer_timeout_as_indeterminate_not_budget_failure():
    class TimedOutClient:
        local_peer_id = ECOSCAN_PEER_ID
        remote_peer_id = OWNER_PEER_ID
        scopes = frozenset({REQUIRED_SCOPE})
        def invoke(self, *args, **kwargs):
            error = RuntimeError("peer request timed out")
            error.code = "peer.timeout"
            raise error
    source = _source(timeout_seconds=5)
    adapter = OBISBridgeAdapter(TimedOutClient(), "http://127.0.0.1:8080")
    with pytest.raises(TransportOutcomeUnknown):
        adapter.scan(_context(source))



def test_ecoscan_adapter_scans_through_independent_go_obis_v02_peer(tmp_path):
    from obis_bridge.v02 import OBISV02Client
    binary = os.environ.get("OBIS_GO_PEER_BINARY")
    if not binary or not os.path.isfile(binary):
        pytest.skip("independent Go peer binary is built by the repository CI workflow")

    command = [
        binary, "server-v02",
        "--peer-id", OWNER_PEER_ID,
        "--listen", "127.0.0.1:0",
        "--key-id", "ecoscan-dev-key",
        "--remote-peer", ECOSCAN_PEER_ID,
        "--principal", "principal:ecoscan",
        "--secret-hex", SECRET.hex(),
        "--scopes", REQUIRED_SCOPE,
        "--required-scope", REQUIRED_SCOPE,
        "--ledger-path", str(tmp_path / "go-obis-operations.json"),
        "--allowed-resource", f"{PROJECT_ID}/{SOURCE_ID}",
    ]
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        assert process.stdout is not None
        address = process.stdout.readline().strip()
        if not address:
            stderr = process.stderr.read() if process.stderr else ""
            raise AssertionError(f"Go OBIS 0.2 peer did not publish its address: {stderr}")
        client = OBISV02Client(
            ECOSCAN_PEER_ID, OWNER_PEER_ID, "ecoscan-dev-key",
            "principal:ecoscan", SECRET, {REQUIRED_SCOPE}, timeout=3.0,
        )
        adapter = OBISBridgeAdapter(OBISV02Invoker(client), f"http://{address}")
        source = _source()
        adapter.validate_config(source)
        result = adapter.scan(_context(source))
        assert result.coverage_state == "COMPLETE"
        assert result.items_seen == 2
        assert result.pages_seen == 1
        assert {item["kind"]: item["value"] for item in result.measurements} == {
            "logical_bytes": 4096,
            "file_count": 2,
        }
        assert all(item["project_id"] == PROJECT_ID for item in result.measurements)
        assert all(item["source_id"] == SOURCE_ID for item in result.measurements)
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


GO_PEER_BINARY = os.environ.get("OBIS_GO_PEER_BINARY")


def _start_independent_go_ecoscan_peer():
    if not GO_PEER_BINARY or not os.path.isfile(GO_PEER_BINARY):
        pytest.skip("independent Go OBIS peer binary is built by repository CI")
    command = [
        GO_PEER_BINARY,
        "--peer-id", OWNER_PEER_ID,
        "--listen", "127.0.0.1:0",
        "--key-id", "ecoscan-dev-key",
        "--remote-peer", ECOSCAN_PEER_ID,
        "--principal", "principal:ecoscan",
        "--secret-hex", SECRET.hex(),
        "--scopes", REQUIRED_SCOPE,
        "--allowed-resource", f"{PROJECT_ID}/{SOURCE_ID}",
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert process.stdout is not None
    address = process.stdout.readline().strip()
    if not address:
        stderr = process.stderr.read() if process.stderr else ""
        process.kill()
        raise AssertionError(f"independent Go OBIS peer failed to publish loopback address: {stderr}")
    return process, f"http://{address}"


def test_ecoscan_adapter_scans_independent_go_peer_over_loopback():
    process, endpoint = _start_independent_go_ecoscan_peer()
    try:
        adapter = OBISBridgeAdapter(_client(), endpoint)
        source = _source()
        adapter.validate_config(source)
        result = adapter.scan(_context(source))
    finally:
        process.terminate()
        process.wait(timeout=5)

    assert result.coverage_state == "COMPLETE"
    assert result.items_seen == 2
    assert result.pages_seen == 1
    assert {item["kind"]: item["value"] for item in result.measurements} == {
        "logical_bytes": 4096,
        "file_count": 2,
    }
    assert all(item["project_id"] == PROJECT_ID for item in result.measurements)
    assert all(item["source_id"] == SOURCE_ID for item in result.measurements)


def test_ecoscan_adapter_go_peer_rejects_ungranted_resource_before_execution():
    process, endpoint = _start_independent_go_ecoscan_peer()
    try:
        adapter = OBISBridgeAdapter(_client(), endpoint)
        source = _source(source_id="different-source")
        adapter.validate_config(source)
        with pytest.raises(OBISRequestError) as raised:
            adapter.scan(_context(source))
    finally:
        process.terminate()
        process.wait(timeout=5)

    assert raised.value.code == "authorization.denied"
