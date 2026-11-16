import pytest

from tradix.factory_demo import FactoryTask, TaskState, run_demo


def test_demo_reaches_review_with_test_evidence() -> None:
    task = run_demo()
    assert task.state is TaskState.REVIEW
    assert [event.sequence for event in task.events] == [1, 2, 3, 4]
    assert task.events[-1].evidence == "demo-tests:passed"


def test_review_gate_rejects_missing_evidence_without_mutating_task() -> None:
    task = FactoryTask(title="test", task_id="test-001")
    task.transition(TaskState.PLANNED, actor="planner")
    task.transition(TaskState.IMPLEMENTING, actor="implementer")
    task.transition(TaskState.TESTING, actor="tester")

    with pytest.raises(ValueError, match="evidence_required"):
        task.transition(TaskState.REVIEW, actor="tester")

    assert task.state is TaskState.TESTING
    assert len(task.events) == 3


def test_candidate_gate_requires_human_approval() -> None:
    task = run_demo()

    with pytest.raises(ValueError, match="human_approval_required"):
        task.transition(
            TaskState.CANDIDATE,
            actor="implementer",
            evidence="review-report:passed",
        )

    assert task.state is TaskState.REVIEW

    task.transition(
        TaskState.CANDIDATE,
        actor="human-reviewer",
        evidence="review-report:passed",
        human_approval="approved-by-human",
    )
    assert task.state is TaskState.CANDIDATE


def test_terminal_state_cannot_be_reopened() -> None:
    task = FactoryTask(title="test", task_id="test-002")
    task.transition(TaskState.CANCELLED, actor="human")

    with pytest.raises(ValueError, match="transition_not_allowed"):
        task.transition(TaskState.PLANNED, actor="factory")

    assert task.state is TaskState.CANCELLED
