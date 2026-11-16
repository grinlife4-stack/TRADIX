import pytest

from tradix.factory.mission_contract import (
    MissionContractError,
    MissionEnvelope,
    TaskPlan,
)


def valid_mission_payload():
    return {
        "mission_id": "mission-001",
        "project_key": "metal-press",
        "version": 1,
        "title": "Develop a first production line",
        "objective": "Design and validate a small production line for aluminium containers.",
        "acceptance_criteria": [
            "The process flow is documented.",
            "A tested prototype meets the agreed dimensional criteria.",
        ],
        "constraints": ["No debt-funded equipment purchases."],
        "risk_class": "low",
        "approval_required": False,
        "budget_currency": "USD",
        "budget_limit_minor": 0,
    }


def valid_task(task_id, title):
    return {
        "task_id": task_id,
        "project_key": "metal-press",
        "title": title,
        "request": f"Complete the {title.lower()} work package.",
        "acceptance_criteria": [f"{title} is independently checked."],
        "risk_class": "low",
        "approval_required": False,
    }


def valid_plan_payload():
    return {
        "mission_id": "mission-001",
        "mission_version": 1,
        "plan_version": 1,
        "project_key": "metal-press",
        "tasks": [
            valid_task("task-production", "Production design"),
            valid_task("task-requirements", "Requirements baseline"),
            valid_task("task-quality", "Quality plan"),
        ],
        "dependencies": [
            {"depends_on": "task-requirements", "task_id": "task-production"},
            {"depends_on": "task-production", "task_id": "task-quality"},
        ],
    }


def test_mission_envelope_accepts_a_general_physical_product_mission():
    mission = MissionEnvelope.from_mapping(valid_mission_payload())

    assert mission.project_key == "metal-press"
    assert mission.risk_class.value == "low"
    assert mission.budget_limit_minor == 0


def test_high_risk_mission_requires_human_approval():
    payload = valid_mission_payload()
    payload["risk_class"] = "critical"

    with pytest.raises(MissionContractError, match="require human approval"):
        MissionEnvelope.from_mapping(payload)


def test_budget_currency_and_limit_must_be_provided_together():
    payload = valid_mission_payload()
    payload.pop("budget_limit_minor")

    with pytest.raises(MissionContractError, match="provided together"):
        MissionEnvelope.from_mapping(payload)


def test_unknown_mission_fields_fail_closed():
    payload = valid_mission_payload()
    payload["execute_shell"] = "untrusted input"

    with pytest.raises(MissionContractError, match="unknown mission fields"):
        MissionEnvelope.from_mapping(payload)


def test_task_plan_validates_mission_and_returns_deterministic_dependency_order():
    mission = MissionEnvelope.from_mapping(valid_mission_payload())
    plan = TaskPlan.from_mapping(valid_plan_payload(), mission)

    assert plan.topological_order() == (
        "task-requirements",
        "task-production",
        "task-quality",
    )


def test_task_plan_rejects_cross_project_tasks():
    mission = MissionEnvelope.from_mapping(valid_mission_payload())
    payload = valid_plan_payload()
    payload["tasks"][0]["project_key"] = "other-product"

    with pytest.raises(MissionContractError, match="plan's project"):
        TaskPlan.from_mapping(payload, mission)


def test_task_plan_rejects_unknown_dependency_references():
    mission = MissionEnvelope.from_mapping(valid_mission_payload())
    payload = valid_plan_payload()
    payload["dependencies"][0]["depends_on"] = "missing-task"

    with pytest.raises(MissionContractError, match="unknown task"):
        TaskPlan.from_mapping(payload, mission)


def test_task_plan_rejects_dependency_cycles():
    mission = MissionEnvelope.from_mapping(valid_mission_payload())
    payload = valid_plan_payload()
    payload["dependencies"] = [
        {"depends_on": "task-requirements", "task_id": "task-production"},
        {"depends_on": "task-production", "task_id": "task-quality"},
        {"depends_on": "task-quality", "task_id": "task-requirements"},
    ]

    with pytest.raises(MissionContractError, match="contains a cycle"):
        TaskPlan.from_mapping(payload, mission)


def test_task_plan_must_target_exact_mission_version():
    mission = MissionEnvelope.from_mapping(valid_mission_payload())
    payload = valid_plan_payload()
    payload["mission_version"] = 2

    with pytest.raises(MissionContractError, match="exact mission ID and version"):
        TaskPlan.from_mapping(payload, mission)


def test_task_plan_rejects_duplicate_dependencies():
    mission = MissionEnvelope.from_mapping(valid_mission_payload())
    payload = valid_plan_payload()
    payload["dependencies"].append(payload["dependencies"][0])

    with pytest.raises(MissionContractError, match="duplicate task dependency"):
        TaskPlan.from_mapping(payload, mission)
