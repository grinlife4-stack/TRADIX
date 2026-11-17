"""Validated mission envelopes and dependency-aware task plans.

This module is a pure Factory Core contract: it validates proposed work but
does not persist, schedule, approve, or execute it.
"""
from __future__ import annotations

from dataclasses import dataclass
import heapq
import re
from typing import Any, Mapping

from .task_contract import RiskClass, TaskContractError, TaskEnvelope


_PROJECT_KEY = re.compile(r"^[a-z][a-z0-9-]{1,39}$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")


class MissionContractError(ValueError):
    """Raised when a mission or proposed task plan is invalid."""


@dataclass(frozen=True, slots=True)
class MissionEnvelope:
    mission_id: str
    project_key: str
    version: int
    title: str
    objective: str
    acceptance_criteria: tuple[str, ...]
    constraints: tuple[str, ...] = ()
    risk_class: RiskClass = RiskClass.LOW
    approval_required: bool = False
    budget_currency: str | None = None
    budget_limit_minor: int | None = None

    def __post_init__(self) -> None:
        for name, value, maximum in (
            ("mission_id", self.mission_id, 80),
            ("title", self.title, 160),
            ("objective", self.objective, 12000),
        ):
            if not isinstance(value, str) or not value.strip() or len(value) > maximum:
                raise MissionContractError(f"{name} must contain 1..{maximum} characters")

        if not isinstance(self.project_key, str) or not _PROJECT_KEY.fullmatch(self.project_key):
            raise MissionContractError("project_key must be a lowercase slug (2..40 characters)")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise MissionContractError("version must be a positive integer")
        if not isinstance(self.acceptance_criteria, tuple) or not 1 <= len(self.acceptance_criteria) <= 30:
            raise MissionContractError("acceptance_criteria must contain 1..30 strings")
        if any(
            not isinstance(item, str) or not item.strip() or len(item) > 500
            for item in self.acceptance_criteria
        ):
            raise MissionContractError("each acceptance criterion must contain 1..500 characters")
        if not isinstance(self.constraints, tuple) or len(self.constraints) > 30:
            raise MissionContractError("constraints must be a tuple containing at most 30 strings")
        if any(
            not isinstance(item, str) or not item.strip() or len(item) > 500
            for item in self.constraints
        ):
            raise MissionContractError("each constraint must contain 1..500 characters")
        if not isinstance(self.risk_class, RiskClass):
            raise MissionContractError("risk_class must be a RiskClass value")
        if not isinstance(self.approval_required, bool):
            raise MissionContractError("approval_required must be a boolean")
        if self.risk_class in (RiskClass.HIGH, RiskClass.CRITICAL) and not self.approval_required:
            raise MissionContractError("high and critical risk missions require human approval")

        if (self.budget_currency is None) != (self.budget_limit_minor is None):
            raise MissionContractError("budget_currency and budget_limit_minor must be provided together")
        if self.budget_currency is not None and (
            not isinstance(self.budget_currency, str) or not _CURRENCY.fullmatch(self.budget_currency)
        ):
            raise MissionContractError("budget_currency must be a three-letter uppercase currency code")
        if self.budget_limit_minor is not None and (
            isinstance(self.budget_limit_minor, bool)
            or not isinstance(self.budget_limit_minor, int)
            or self.budget_limit_minor < 0
        ):
            raise MissionContractError("budget_limit_minor must be a non-negative integer")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MissionEnvelope":
        if not isinstance(value, Mapping):
            raise MissionContractError("mission must be an object")
        required = {
            "mission_id", "project_key", "version", "title",
            "objective", "acceptance_criteria",
        }
        optional = {
            "constraints", "risk_class", "approval_required",
            "budget_currency", "budget_limit_minor",
        }
        unknown = set(value) - required - optional
        missing = required - set(value)
        if unknown:
            raise MissionContractError(f"unknown mission fields: {', '.join(sorted(unknown))}")
        if missing:
            raise MissionContractError(f"missing mission fields: {', '.join(sorted(missing))}")

        criteria = value["acceptance_criteria"]
        constraints = value.get("constraints", ())
        if not isinstance(criteria, (list, tuple)) or any(not isinstance(x, str) for x in criteria):
            raise MissionContractError("acceptance_criteria must be a list of strings")
        if not isinstance(constraints, (list, tuple)) or any(not isinstance(x, str) for x in constraints):
            raise MissionContractError("constraints must be a list of strings")
        try:
            risk = RiskClass(value.get("risk_class", RiskClass.LOW.value))
        except (TypeError, ValueError) as exc:
            raise MissionContractError("risk_class must be low, medium, high, or critical") from exc

        return cls(
            mission_id=value["mission_id"],
            project_key=value["project_key"],
            version=value["version"],
            title=value["title"],
            objective=value["objective"],
            acceptance_criteria=tuple(criteria),
            constraints=tuple(constraints),
            risk_class=risk,
            approval_required=value.get("approval_required", False),
            budget_currency=value.get("budget_currency"),
            budget_limit_minor=value.get("budget_limit_minor"),
        )


@dataclass(frozen=True, slots=True)
class TaskDependency:
    """The task_id cannot start until depends_on has completed its required work."""

    depends_on: str
    task_id: str

    def __post_init__(self) -> None:
        for name, value in (("depends_on", self.depends_on), ("task_id", self.task_id)):
            if not isinstance(value, str) or not value.strip() or len(value) > 80:
                raise MissionContractError(f"{name} must contain 1..80 characters")
        if self.depends_on == self.task_id:
            raise MissionContractError("a task cannot depend on itself")


@dataclass(frozen=True, slots=True)
class TaskPlan:
    mission_id: str
    mission_version: int
    plan_version: int
    project_key: str
    tasks: tuple[TaskEnvelope, ...]
    dependencies: tuple[TaskDependency, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.mission_id, str) or not self.mission_id.strip() or len(self.mission_id) > 80:
            raise MissionContractError("mission_id must contain 1..80 characters")
        for name, value in (("mission_version", self.mission_version), ("plan_version", self.plan_version)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise MissionContractError(f"{name} must be a positive integer")
        if not isinstance(self.project_key, str) or not _PROJECT_KEY.fullmatch(self.project_key):
            raise MissionContractError("project_key must be a lowercase slug (2..40 characters)")
        if not isinstance(self.tasks, tuple) or not 1 <= len(self.tasks) <= 100:
            raise MissionContractError("tasks must contain 1..100 TaskEnvelope values")
        if any(not isinstance(task, TaskEnvelope) for task in self.tasks):
            raise MissionContractError("tasks must contain only validated TaskEnvelope values")
        task_ids = [task.task_id for task in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise MissionContractError("task IDs must be unique within a plan")
        if any(task.project_key != self.project_key for task in self.tasks):
            raise MissionContractError("every task must belong to the plan's project")
        if not isinstance(self.dependencies, tuple) or len(self.dependencies) > 500:
            raise MissionContractError("dependencies must be a tuple containing at most 500 edges")
        if any(not isinstance(edge, TaskDependency) for edge in self.dependencies):
            raise MissionContractError("dependencies must contain TaskDependency values")

        known_ids = set(task_ids)
        seen_edges: set[tuple[str, str]] = set()
        for edge in self.dependencies:
            pair = (edge.depends_on, edge.task_id)
            if pair in seen_edges:
                raise MissionContractError("duplicate task dependency")
            seen_edges.add(pair)
            if edge.depends_on not in known_ids or edge.task_id not in known_ids:
                raise MissionContractError("task dependency references an unknown task")

        self.topological_order()

    def validate_for(self, mission: MissionEnvelope) -> None:
        if not isinstance(mission, MissionEnvelope):
            raise MissionContractError("mission must be a validated MissionEnvelope")
        if self.mission_id != mission.mission_id or self.mission_version != mission.version:
            raise MissionContractError("task plan must target the exact mission ID and version")
        if self.project_key != mission.project_key:
            raise MissionContractError("task plan project does not match the mission project")

    def topological_order(self) -> tuple[str, ...]:
        """Return a deterministic dependency-respecting order or reject cycles."""
        task_ids = [task.task_id for task in self.tasks]
        outgoing = {task_id: [] for task_id in task_ids}
        incoming = {task_id: 0 for task_id in task_ids}
        for edge in self.dependencies:
            outgoing[edge.depends_on].append(edge.task_id)
            incoming[edge.task_id] += 1

        ready = [task_id for task_id, count in incoming.items() if count == 0]
        heapq.heapify(ready)
        ordered: list[str] = []
        while ready:
            current = heapq.heappop(ready)
            ordered.append(current)
            for dependent in sorted(outgoing[current]):
                incoming[dependent] -= 1
                if incoming[dependent] == 0:
                    heapq.heappush(ready, dependent)

        if len(ordered) != len(task_ids):
            raise MissionContractError("task dependency graph contains a cycle")
        return tuple(ordered)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any], mission: MissionEnvelope) -> "TaskPlan":
        if not isinstance(value, Mapping):
            raise MissionContractError("task plan must be an object")
        if not isinstance(mission, MissionEnvelope):
            raise MissionContractError("mission must be a validated MissionEnvelope")
        expected = {
            "mission_id", "mission_version", "plan_version",
            "project_key", "tasks", "dependencies",
        }
        unknown = set(value) - expected
        missing = expected - set(value)
        if unknown:
            raise MissionContractError(f"unknown plan fields: {', '.join(sorted(unknown))}")
        if missing:
            raise MissionContractError(f"missing plan fields: {', '.join(sorted(missing))}")

        raw_tasks = value["tasks"]
        raw_dependencies = value["dependencies"]
        if not isinstance(raw_tasks, list) or not isinstance(raw_dependencies, list):
            raise MissionContractError("tasks and dependencies must be arrays")
        try:
            tasks = tuple(TaskEnvelope.from_mapping(item) for item in raw_tasks)
        except (TaskContractError, TypeError) as exc:
            raise MissionContractError("task plan contains an invalid task envelope") from exc

        dependencies: list[TaskDependency] = []
        for item in raw_dependencies:
            if not isinstance(item, dict) or set(item) != {"depends_on", "task_id"}:
                raise MissionContractError("each dependency must contain exactly depends_on and task_id")
            dependencies.append(TaskDependency(**item))

        plan = cls(
            mission_id=value["mission_id"],
            mission_version=value["mission_version"],
            plan_version=value["plan_version"],
            project_key=value["project_key"],
            tasks=tasks,
            dependencies=tuple(dependencies),
        )
        plan.validate_for(mission)
        return plan
