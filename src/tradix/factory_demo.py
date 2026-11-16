"""Small, deterministic task lifecycle used to test the TRADIX factory loop.

This module is an in-memory demonstration, not the production orchestrator.
It deliberately refuses progression when required evidence is missing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class TaskState(StrEnum):
    QUEUED = "queued"
    PLANNED = "planned"
    IMPLEMENTING = "implementing"
    TESTING = "testing"
    REVIEW = "review"
    CANDIDATE = "candidate"
    DEPLOYED_TEST = "deployed_test"
    VERIFIED = "verified"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"


_ALLOWED: dict[TaskState, set[TaskState]] = {
    TaskState.QUEUED: {TaskState.PLANNED, TaskState.BLOCKED, TaskState.CANCELLED},
    TaskState.PLANNED: {TaskState.IMPLEMENTING, TaskState.BLOCKED, TaskState.CANCELLED},
    TaskState.IMPLEMENTING: {
        TaskState.TESTING, TaskState.BLOCKED, TaskState.FAILED, TaskState.CANCELLED
    },
    TaskState.TESTING: {
        TaskState.REVIEW, TaskState.IMPLEMENTING, TaskState.BLOCKED,
        TaskState.FAILED, TaskState.CANCELLED
    },
    TaskState.REVIEW: {
        TaskState.CANDIDATE, TaskState.IMPLEMENTING, TaskState.BLOCKED,
        TaskState.FAILED, TaskState.CANCELLED
    },
    TaskState.CANDIDATE: {
        TaskState.DEPLOYED_TEST, TaskState.BLOCKED, TaskState.CANCELLED
    },
    TaskState.DEPLOYED_TEST: {
        TaskState.VERIFIED, TaskState.BLOCKED, TaskState.FAILED,
        TaskState.CANCELLED
    },
    TaskState.VERIFIED: set(),
    TaskState.BLOCKED: set(),
    TaskState.FAILED: set(),
    TaskState.CANCELLED: set(),
}


@dataclass(frozen=True, slots=True)
class TaskEvent:
    sequence: int
    previous: TaskState
    current: TaskState
    actor: str
    evidence: str | None = None


@dataclass(slots=True)
class FactoryTask:
    title: str
    task_id: str
    state: TaskState = TaskState.QUEUED
    events: list[TaskEvent] = field(default_factory=list)

    def transition(
        self,
        target: TaskState,
        *,
        actor: str,
        evidence: str | None = None,
        human_approval: str | None = None,
    ) -> TaskEvent:
        if not actor.strip():
            raise ValueError("actor_required")
        if target not in _ALLOWED[self.state]:
            raise ValueError(f"transition_not_allowed:{self.state}->{target}")

        if target in {
            TaskState.REVIEW,
            TaskState.CANDIDATE,
            TaskState.DEPLOYED_TEST,
            TaskState.VERIFIED,
        } and not (evidence and evidence.strip()):
            raise ValueError("evidence_required")

        if target is TaskState.CANDIDATE and not (
            human_approval and human_approval.strip()
        ):
            raise ValueError("human_approval_required")

        event = TaskEvent(
            sequence=len(self.events) + 1,
            previous=self.state,
            current=target,
            actor=actor,
            evidence=evidence,
        )
        self.events.append(event)
        self.state = target
        return event


def run_demo() -> FactoryTask:
    """Run a safe demo through testing, then stop at the independent review gate."""
    task = FactoryTask(title="First TRADIX factory demo", task_id="demo-001")
    task.transition(TaskState.PLANNED, actor="factory-demo")
    task.transition(TaskState.IMPLEMENTING, actor="factory-demo")
    task.transition(TaskState.TESTING, actor="factory-demo")
    task.transition(
        TaskState.REVIEW,
        actor="test-engineer",
        evidence="demo-tests:passed",
    )
    return task


if __name__ == "__main__":
    demo = run_demo()
    print(f"task_id={demo.task_id}")
    print(f"state={demo.state.value}")
    print(f"events={len(demo.events)}")
