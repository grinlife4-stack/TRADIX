import pytest

from tradix.factory.task_contract import (
    RiskClass,
    TaskContractError,
    TaskEnvelope,
    TaskState,
    transition_task,
)


def valid_payload():
    return {
        "task_id": "task-001",
        "project_key": "tradix",
        "repository": "grinlife4-stack/TRADIX",
        "base_ref": "main",
        "title": "Add a bounded task contract",
        "request": "Validate task input and lifecycle transitions.",
        "acceptance_criteria": ["Invalid input is rejected", "Evidence gates are enforced"],
        "risk_class": "low",
        "approval_required": False,
    }


def test_valid_task_envelope_is_parsed():
    task = TaskEnvelope.from_mapping(valid_payload())
    assert task.project_key == "tradix"
    assert task.risk_class is RiskClass.LOW
    assert task.acceptance_criteria[0] == "Invalid input is rejected"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("project_key", "TRADIX"),
        ("repository", "TRADIX"),
        ("acceptance_criteria", []),
        ("risk_class", "extreme"),
        ("approval_required", "false"),
    ],
)
def test_invalid_task_fields_are_rejected(field, value):
    payload = valid_payload()
    payload[field] = value
    with pytest.raises(TaskContractError):
        TaskEnvelope.from_mapping(payload)


def test_unknown_fields_fail_closed():
    payload = valid_payload()
    payload["run_shell"] = "rm -rf /"
    with pytest.raises(TaskContractError, match="unknown task fields"):
        TaskEnvelope.from_mapping(payload)


@pytest.mark.parametrize("risk", ["high", "critical"])
def test_high_risk_requires_human_approval(risk):
    payload = valid_payload()
    payload["risk_class"] = risk
    with pytest.raises(TaskContractError, match="require human approval"):
        TaskEnvelope.from_mapping(payload)


def test_testing_cannot_enter_review_without_test_evidence():
    with pytest.raises(TaskContractError, match="test_report"):
        transition_task(TaskState.TESTING, TaskState.REVIEW)


def test_review_cannot_approve_candidate_without_review_evidence():
    with pytest.raises(TaskContractError, match="review_report"):
        transition_task(TaskState.REVIEW, TaskState.CANDIDATE, ("",))


def test_review_evidence_allows_candidate_transition():
    assert transition_task(
        TaskState.REVIEW, TaskState.CANDIDATE, ("b2://artifacts/review.json",)
    ) is TaskState.CANDIDATE


def test_deployed_test_requires_health_evidence_for_verification():
    with pytest.raises(TaskContractError, match="health_check"):
        transition_task(TaskState.DEPLOYED_TEST, TaskState.VERIFIED)


def test_terminal_state_cannot_be_reopened():
    with pytest.raises(TaskContractError, match="not allowed"):
        transition_task(TaskState.VERIFIED, TaskState.IMPLEMENTING)


def test_blocked_task_can_resume_only_to_planned():
    assert transition_task(TaskState.BLOCKED, TaskState.PLANNED) is TaskState.PLANNED
    with pytest.raises(TaskContractError, match="not allowed"):
        transition_task(TaskState.BLOCKED, TaskState.IMPLEMENTING)
