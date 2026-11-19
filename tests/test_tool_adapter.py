from dataclasses import replace

import pytest

from tradix.tools.adapter import (
    AdapterContractError, AdapterHealth, AdapterResult, ResourceLimits,
    ToolInvocation, ToolAdapter, validate_adapter,
)


SHA = "a" * 40


class FakeAdapter:
    tool_id = "pytest"
    tool_version = "8.3.0"
    adapter_version = "1.0.0"
    supported_job_types = ("python.tests", "python.lint")

    def health_check(self):
        return AdapterHealth("healthy", "2026-11-19T18:00:00Z", self.adapter_version)

    def execute(self, invocation):
        invocation.validate(self.supported_job_types)
        return AdapterResult(
            run_id=invocation.run_id,
            status="succeeded",
            started_at="2026-11-19T18:00:00Z",
            finished_at="2026-11-19T18:00:01Z",
            source_commit_sha=invocation.source_commit_sha,
            evidence_refs=("evidence://runs/1/test-report",),
        )

    def cancel(self, run_id):
        return True

    def collect_logs(self, run_id):
        return ("tests completed",)


def invocation(**overrides):
    values = dict(
        run_id="run-001",
        tool_id="pytest",
        tool_version="8.3.0",
        job_type="python.tests",
        source_commit_sha=SHA,
        input_refs=("evidence://source/archive",),
        idempotency_key="task-001-attempt-1",
    )
    values.update(overrides)
    return ToolInvocation(**values)


def test_adapter_contract_and_result_validation():
    adapter = FakeAdapter()
    validate_adapter(adapter)
    request = invocation()
    request.validate(adapter.supported_job_types)
    result = adapter.execute(request)
    result.validate(request)
    assert result.status == "succeeded"
    assert adapter.cancel("run-001") is True
    assert adapter.collect_logs("run-001") == ("tests completed",)


def test_arbitrary_job_type_rejected():
    request = invocation(job_type="shell.execute")
    with pytest.raises(AdapterContractError, match="unrestricted"):
        request.validate(FakeAdapter.supported_job_types)


@pytest.mark.parametrize("limits", [
    ResourceLimits(cpu_millis=0),
    ResourceLimits(memory_mb=1),
    ResourceLimits(timeout_seconds=3601),
    ResourceLimits(network_enabled=1),
])
def test_resource_limits_fail_closed(limits):
    with pytest.raises(AdapterContractError):
        limits.validate()


@pytest.mark.parametrize("ref", [
    "file:///etc/passwd",
    "https://user:pass@example.com/input",
    "not-a-reference",
])
def test_invocation_rejects_unsafe_input_refs(ref):
    with pytest.raises(AdapterContractError):
        invocation(input_refs=(ref,)).validate(FakeAdapter.supported_job_types)


def test_invocation_requires_full_source_sha():
    with pytest.raises(AdapterContractError):
        invocation(source_commit_sha="abc").validate(FakeAdapter.supported_job_types)


def test_success_requires_evidence():
    request = invocation()
    result = AdapterResult(
        run_id=request.run_id,
        status="succeeded",
        started_at="start",
        finished_at="end",
        source_commit_sha=request.source_commit_sha,
    )
    with pytest.raises(AdapterContractError, match="evidence"):
        result.validate(request)


def test_result_must_match_source_and_run():
    request = invocation()
    result = AdapterResult(
        run_id="other-run",
        status="failed",
        started_at="start",
        finished_at="end",
        source_commit_sha="b" * 40,
        error_code="TEST_FAILURE",
    )
    with pytest.raises(AdapterContractError):
        result.validate(request)


def test_failed_result_requires_normalized_error_code():
    request = invocation()
    result = AdapterResult(
        run_id=request.run_id,
        status="failed",
        started_at="start",
        finished_at="end",
        source_commit_sha=request.source_commit_sha,
    )
    with pytest.raises(AdapterContractError, match="error_code"):
        result.validate(request)


def test_invalid_adapter_job_allowlist_rejected():
    adapter = FakeAdapter()
    adapter.supported_job_types = ("shell.execute",)
    with pytest.raises(AdapterContractError):
        validate_adapter(adapter)


def test_protocol_runtime_check():
    assert isinstance(FakeAdapter(), ToolAdapter)
