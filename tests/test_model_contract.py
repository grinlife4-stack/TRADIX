import json

import pytest

from tradix.factory.model_contract import (
    ModelContractError,
    ModelRequest,
    ModelResponse,
    PlanDocument,
)


def response(text):
    return ModelResponse(
        provider="fake",
        model_id="fake-v1",
        output_text=text,
        request_id="req-001",
    )


def valid_plan():
    return {
        "summary": "Add a validated task contract.",
        "steps": [
            {
                "step_id": "S1",
                "action": "Inspect the task contract.",
                "rationale": "Establish current behavior.",
                "acceptance_check": "Existing tests pass.",
            }
        ],
    }


def test_model_request_validates_bounds():
    request = ModelRequest(
        task_id="task-1",
        purpose="planning",
        instructions="Return a JSON plan.",
        input_text="Implement a parser.",
        model_id="provider/model",
    )
    assert request.timeout_seconds == 60


def test_model_request_rejects_invalid_timeout():
    with pytest.raises(ModelContractError, match="timeout_seconds"):
        ModelRequest("t", "p", "i", "x", "m", timeout_seconds=0)


def test_model_response_rejects_negative_token_counts():
    with pytest.raises(ModelContractError, match="input_tokens"):
        ModelResponse("p", "m", "{}", "r", input_tokens=-1)


def test_valid_model_plan_is_parsed():
    plan = PlanDocument.from_model_response(response(json.dumps(valid_plan())))
    assert plan.summary == "Add a validated task contract."
    assert plan.steps[0].step_id == "S1"


def test_invalid_json_is_rejected():
    with pytest.raises(ModelContractError, match="valid JSON"):
        PlanDocument.from_model_response(response("not json"))


def test_extra_top_level_field_is_rejected():
    payload = valid_plan()
    payload["shell_command"] = "unsafe"
    with pytest.raises(ModelContractError, match="exactly summary and steps"):
        PlanDocument.from_model_response(response(json.dumps(payload)))


def test_extra_step_field_is_rejected():
    payload = valid_plan()
    payload["steps"][0]["tool_call"] = {"name": "shell"}
    with pytest.raises(ModelContractError, match="exactly the four documented fields"):
        PlanDocument.from_model_response(response(json.dumps(payload)))


def test_duplicate_step_ids_are_rejected():
    payload = valid_plan()
    payload["steps"].append(dict(payload["steps"][0]))
    with pytest.raises(ModelContractError, match="unique"):
        PlanDocument.from_model_response(response(json.dumps(payload)))


def test_empty_plan_is_rejected():
    payload = valid_plan()
    payload["steps"] = []
    with pytest.raises(ModelContractError, match="1..20"):
        PlanDocument.from_model_response(response(json.dumps(payload)))



def test_boolean_timeout_is_rejected():
    with pytest.raises(ModelContractError, match="timeout_seconds"):
        ModelRequest("t", "p", "i", "x", "m", timeout_seconds=True)


def test_boolean_token_count_is_rejected():
    with pytest.raises(ModelContractError, match="input_tokens"):
        ModelResponse("p", "m", "{}", "r", input_tokens=True)


def test_oversized_model_output_is_rejected():
    with pytest.raises(ModelContractError, match="100000"):
        ModelResponse("p", "m", "x" * 100001, "r")
