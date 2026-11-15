"""Validated task input and evidence-gated lifecycle transitions.

This module is intentionally pure: it performs no I/O, network access, or
persistence. Orchestration and durable event recording belong to later layers.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Any, Mapping


_PROJECT_KEY = re.compile(r"^[a-z][a-z0-9-]{1,39}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class TaskContractError(ValueError):
    """Raised when task input or a requested lifecycle transition is invalid."""


class RiskClass(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskState(str, Enum):
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


@dataclass(frozen=True, slots=True)
class TaskEnvelope:
    task_id: str
    project_key: str
    repository: str
    base_ref: str
    title: str
    request: str
    acceptance_criteria: tuple[str, ...]
    risk_class: RiskClass
    approval_required: bool

    def __post_init__(self) -> None:
        text_fields = (self.task_id, self.project_key, self.repository, self.base_ref, self.title, self.request)
        if any(not isinstance(value, str) for value in text_fields):
            raise TaskContractError("task identity and text fields must be strings")
        if not isinstance(self.acceptance_criteria, tuple) or any(
            not isinstance(item, str) for item in self.acceptance_criteria
        ):
            raise TaskContractError("acceptance_criteria must be a tuple of strings")
        if not isinstance(self.risk_class, RiskClass):
            raise TaskContractError("risk_class must be a RiskClass value")
        if not isinstance(self.approval_required, bool):
            raise TaskContractError("approval_required must be a boolean")
        if not self.task_id.strip() or len(self.task_id) > 80:
            raise TaskContractError("task_id must contain 1..80 non-whitespace characters")
        if not _PROJECT_KEY.fullmatch(self.project_key):
            raise TaskContractError("project_key must be a lowercase slug (2..40 characters)")
        if not _REPOSITORY.fullmatch(self.repository):
            raise TaskContractError("repository must use owner/name format")
        if not self.base_ref.strip() or len(self.base_ref) > 255:
            raise TaskContractError("base_ref must contain 1..255 characters")
        if not self.title.strip() or len(self.title) > 160:
            raise TaskContractError("title must contain 1..160 characters")
        if not self.request.strip() or len(self.request) > 12000:
            raise TaskContractError("request must contain 1..12000 characters")
        if not self.acceptance_criteria:
            raise TaskContractError("at least one acceptance criterion is required")
        if len(self.acceptance_criteria) > 30:
            raise TaskContractError("no more than 30 acceptance criteria are allowed")
        if any(not item.strip() or len(item) > 500 for item in self.acceptance_criteria):
            raise TaskContractError("each acceptance criterion must contain 1..500 characters")
        if self.risk_class in (RiskClass.HIGH, RiskClass.CRITICAL) and not self.approval_required:
            raise TaskContractError("high and critical risk tasks require human approval")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "TaskEnvelope":
        expected = {
            "task_id", "project_key", "repository", "base_ref", "title",
            "request", "acceptance_criteria", "risk_class", "approval_required",
        }
        unknown = set(value) - expected
        missing = expected - set(value)
        if unknown:
            raise TaskContractError(f"unknown task fields: {', '.join(sorted(unknown))}")
        if missing:
            raise TaskContractError(f"missing task fields: {', '.join(sorted(missing))}")

        criteria = value["acceptance_criteria"]
        if not isinstance(criteria, (list, tuple)) or any(not isinstance(x, str) for x in criteria):
            raise TaskContractError("acceptance_criteria must be a list of strings")
        if not isinstance(value["approval_required"], bool):
            raise TaskContractError("approval_required must be a boolean")
        try:
            risk = RiskClass(value["risk_class"])
        except (TypeError, ValueError) as exc:
            raise TaskContractError("risk_class must be low, medium, high, or critical") from exc

        string_fields = ("task_id", "project_key", "repository", "base_ref", "title", "request")
        if any(not isinstance(value[field], str) for field in string_fields):
            raise TaskContractError("task identity and text fields must be strings")

        return cls(
            task_id=value["task_id"],
            project_key=value["project_key"],
            repository=value["repository"],
            base_ref=value["base_ref"],
            title=value["title"],
            request=value["request"],
            acceptance_criteria=tuple(criteria),
            risk_class=risk,
            approval_required=value["approval_required"],
        )


_ALLOWED_TRANSITIONS: dict[TaskState, frozenset[TaskState]] = {
    TaskState.QUEUED: frozenset({TaskState.PLANNED, TaskState.BLOCKED, TaskState.FAILED, TaskState.CANCELLED}),
    TaskState.PLANNED: frozenset({TaskState.IMPLEMENTING, TaskState.BLOCKED, TaskState.FAILED, TaskState.CANCELLED}),
    TaskState.IMPLEMENTING: frozenset({TaskState.TESTING, TaskState.BLOCKED, TaskState.FAILED, TaskState.CANCELLED}),
    TaskState.TESTING: frozenset({TaskState.REVIEW, TaskState.IMPLEMENTING, TaskState.BLOCKED, TaskState.FAILED, TaskState.CANCELLED}),
    TaskState.REVIEW: frozenset({TaskState.CANDIDATE, TaskState.IMPLEMENTING, TaskState.BLOCKED, TaskState.FAILED, TaskState.CANCELLED}),
    TaskState.CANDIDATE: frozenset({TaskState.DEPLOYED_TEST, TaskState.VERIFIED, TaskState.BLOCKED, TaskState.FAILED, TaskState.CANCELLED}),
    TaskState.DEPLOYED_TEST: frozenset({TaskState.VERIFIED, TaskState.BLOCKED, TaskState.FAILED, TaskState.CANCELLED}),
    TaskState.BLOCKED: frozenset({TaskState.PLANNED, TaskState.CANCELLED}),
    TaskState.VERIFIED: frozenset(),
    TaskState.FAILED: frozenset(),
    TaskState.CANCELLED: frozenset(),
}

_REQUIRED_EVIDENCE: dict[tuple[TaskState, TaskState], str] = {
    (TaskState.TESTING, TaskState.REVIEW): "test_report",
    (TaskState.REVIEW, TaskState.CANDIDATE): "review_report",
    (TaskState.DEPLOYED_TEST, TaskState.VERIFIED): "health_check",
}


def validate_approval(task: TaskEnvelope, action: str, decision: str | None) -> None:
    """Enforce human approval for flagged tasks and inherently sensitive actions."""
    protected_actions = {
        "production_deploy",
        "destructive_migration",
        "secret_change",
        "permission_change",
        "irreversible_operation",
    }
    if not isinstance(task, TaskEnvelope):
        raise TaskContractError("task must be a validated TaskEnvelope")
    if not isinstance(action, str) or not action.strip():
        raise TaskContractError("action must be a non-empty string")
    if decision not in (None, "approved", "rejected"):
        raise TaskContractError("decision must be approved, rejected, or None")
    if decision == "rejected":
        raise TaskContractError(f"human approval rejected for action: {action}")
    if (task.approval_required or action in protected_actions) and decision != "approved":
        raise TaskContractError(f"human approval is required for action: {action}")


def transition_task(
    task: TaskEnvelope,
    current: TaskState,
    target: TaskState,
    evidence_refs: tuple[str, ...] = (),
    approval_decision: str | None = None,
) -> TaskState:
    """Validate and return the target state; this function never persists it."""
    if not isinstance(task, TaskEnvelope):
        raise TaskContractError("task must be a validated TaskEnvelope")
    if not isinstance(current, TaskState) or not isinstance(target, TaskState):
        raise TaskContractError("current and target must be TaskState values")
    if not isinstance(evidence_refs, tuple) or any(not isinstance(ref, str) for ref in evidence_refs):
        raise TaskContractError("evidence_refs must be a tuple of strings")
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise TaskContractError(f"transition not allowed: {current.value} -> {target.value}")

    if current is TaskState.PLANNED and target is TaskState.IMPLEMENTING and task.approval_required:
        validate_approval(task, "begin_implementation", approval_decision)

    required = _REQUIRED_EVIDENCE.get((current, target))
    if required and not any(ref.strip() for ref in evidence_refs):
        raise TaskContractError(f"{required} evidence reference is required")

    return target
