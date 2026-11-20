from datetime import datetime, timezone
from uuid import uuid4

import pytest

from tradix.tiis import TIISAuthorizationError, TIISValidator
from tradix.tools.adapter import AdapterResult, ResourceLimits, ToolInvocation
from tradix.tools.tiis_adapter import (
    ToolAdapterTIISCodecError,
    invocation_from_tiis,
    invocation_to_tiis,
    result_to_tiis_event,
)


NOW = datetime(2026, 11, 20, 12, 0, 10, tzinfo=timezone.utc)
ORCHESTRATOR = {"project_id": "tradix", "component_id": "factory-orchestrator"}
ADAPTER = {"project_id": "tradix", "component_id": "build-adapter"}
JOB_TYPES = ("build.android",)


def invocation():
    return ToolInvocation(
        run_id="run-001",
        tool_id="android-builder",
        tool_version="1.0.0",
        job_type="build.android",
        source_commit_sha="a" * 40,
        input_refs=("evidence://nexora/source/commit",),
        idempotency_key="mission-run-001",
        limits=ResourceLimits(
            cpu_millis=2000,
            memory_mb=2048,
            timeout_seconds=600,
            network_enabled=False,
            writable_workspace=True,
        ),
    )


def test_tool_invocation_round_trips_through_tiis():
    original = invocation()
    envelope = invocation_to_tiis(
        original,
        sender_component=ORCHESTRATOR,
        recipient_component=ADAPTER,
        supported_job_types=JOB_TYPES,
        now=NOW,
    )
    restored = invocation_from_tiis(
        envelope,
        validator=TIISValidator(authorization_policy=lambda *_args: True),
        authenticated_sender=ORCHESTRATOR,
        expected_recipient=ADAPTER,
        supported_job_types=JOB_TYPES,
        now=NOW,
    )
    assert restored == original


def test_invocation_rejects_job_type_not_allowlisted():
    envelope = invocation_to_tiis(
        invocation(),
        sender_component=ORCHESTRATOR,
        recipient_component=ADAPTER,
        supported_job_types=JOB_TYPES,
        now=NOW,
    )
    with pytest.raises(ToolAdapterTIISCodecError, match="invocation_contract_rejected"):
        invocation_from_tiis(
            envelope,
            validator=TIISValidator(authorization_policy=lambda *_args: True),
            authenticated_sender=ORCHESTRATOR,
            expected_recipient=ADAPTER,
            supported_job_types=("build.ios",),
            now=NOW,
        )


def test_outer_idempotency_key_is_bound_to_domain_invocation():
    envelope = invocation_to_tiis(
        invocation(),
        sender_component=ORCHESTRATOR,
        recipient_component=ADAPTER,
        supported_job_types=JOB_TYPES,
        now=NOW,
    )
    envelope["idempotency_key"] = "another-valid-idempotency-key"
    with pytest.raises(ToolAdapterTIISCodecError, match="idempotency_binding_mismatch"):
        invocation_from_tiis(
            envelope,
            validator=TIISValidator(authorization_policy=lambda *_args: True),
            authenticated_sender=ORCHESTRATOR,
            expected_recipient=ADAPTER,
            supported_job_types=JOB_TYPES,
            now=NOW,
        )


def test_tool_adapter_authorization_is_fail_closed():
    envelope = invocation_to_tiis(
        invocation(),
        sender_component=ORCHESTRATOR,
        recipient_component=ADAPTER,
        supported_job_types=JOB_TYPES,
        now=NOW,
    )
    with pytest.raises(TIISAuthorizationError, match="authorization_policy_not_configured"):
        invocation_from_tiis(
            envelope,
            validator=TIISValidator(),
            authenticated_sender=ORCHESTRATOR,
            expected_recipient=ADAPTER,
            supported_job_types=JOB_TYPES,
            now=NOW,
        )


def test_result_is_emitted_as_correlated_tiis_event():
    call = invocation()
    result = AdapterResult(
        run_id=call.run_id,
        status="succeeded",
        started_at="2026-11-20T12:00:00Z",
        finished_at="2026-11-20T12:00:05Z",
        source_commit_sha=call.source_commit_sha,
        output_refs=("evidence://nexora/artifact/apk",),
        evidence_refs=("evidence://nexora/tests/run-001",),
    )
    event = result_to_tiis_event(
        result,
        call,
        sender_component=ADAPTER,
        recipient_component=ORCHESTRATOR,
        correlation_id=str(uuid4()),
        now=NOW,
    )
    TIISValidator(authorization_policy=lambda *_args: True).validate(
        event,
        authenticated_sender=ADAPTER,
        expected_recipient=ORCHESTRATOR,
        now=NOW,
    )
    assert event["event_type"] == "tool.adapter.result"
    assert event["payload"]["run_id"] == call.run_id


def test_successful_result_without_evidence_is_rejected():
    call = invocation()
    result = AdapterResult(
        run_id=call.run_id,
        status="succeeded",
        started_at="2026-11-20T12:00:00Z",
        finished_at="2026-11-20T12:00:05Z",
        source_commit_sha=call.source_commit_sha,
    )
    with pytest.raises(ValueError, match="require evidence"):
        result_to_tiis_event(
            result,
            call,
            sender_component=ADAPTER,
            recipient_component=ORCHESTRATOR,
            correlation_id=str(uuid4()),
            now=NOW,
        )
