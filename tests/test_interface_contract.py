import json

import pytest

from tradix.factory.interface_contract import (
    FactoryNeed,
    InterfaceContractError,
    InterfaceMessage,
    MessageType,
    NeedCategory,
    NeedPriority,
    Sender,
)


def message(**overrides):
    values = {
        "message_id": "msg-001",
        "conversation_id": "conv-001",
        "project_key": "tradix",
        "correlation_id": "mission-001",
        "sender": Sender.INTERFACE_AI,
        "message_type": MessageType.MISSION_PROPOSAL,
        "body": {"text": "Create a bounded product mission."},
        "created_at": "2026-11-17T19:00:00Z",
    }
    values.update(overrides)
    return InterfaceMessage(**values)


def test_interface_ai_can_submit_a_mission_proposal():
    item = message()
    assert item.sender is Sender.INTERFACE_AI
    assert item.message_type is MessageType.MISSION_PROPOSAL


def test_interface_ai_cannot_emit_a_factory_result_or_approval():
    with pytest.raises(InterfaceContractError, match="not permitted"):
        message(message_type=MessageType.RESULT, body={"summary": "approved"})


def test_user_messages_are_not_confused_with_model_generated_proposals():
    with pytest.raises(InterfaceContractError, match="not permitted"):
        message(sender=Sender.USER, message_type=MessageType.MISSION_PROPOSAL)


def test_factory_need_is_structured_and_validated():
    need = FactoryNeed.from_mapping({
        "need_id": "need-001",
        "project_key": "tradix",
        "category": "missing_information",
        "question": "Which accounting jurisdiction is required?",
        "reason": "Tax and invoice rules depend on jurisdiction.",
        "priority": "high",
        "blocks_progress": True,
        "mission_id": "mission-001",
    })
    assert need.category is NeedCategory.MISSING_INFORMATION
    assert need.priority is NeedPriority.HIGH
    assert need.blocks_progress is True


def test_factory_need_rejects_unknown_fields():
    with pytest.raises(InterfaceContractError, match="unknown factory need fields"):
        FactoryNeed.from_mapping({
            "need_id": "need-001",
            "project_key": "tradix",
            "category": "capability",
            "question": "Need a browser.",
            "reason": "No browser adapter is registered.",
            "execute_shell": True,
        })


def test_factory_message_requires_a_valid_need_payload():
    with pytest.raises(InterfaceContractError, match="missing factory need fields"):
        message(
            sender=Sender.FACTORY,
            message_type=MessageType.FACTORY_NEED,
            body={"question": "Need something"},
        )


def test_factory_result_requires_a_summary():
    with pytest.raises(InterfaceContractError, match="requires body.summary"):
        message(
            sender=Sender.FACTORY,
            message_type=MessageType.RESULT,
            body={"text": "Done"},
        )


def test_message_rejects_invalid_project_scope():
    with pytest.raises(InterfaceContractError, match="project_key"):
        message(project_key="../other-project")


def test_message_rejects_invalid_identifier():
    with pytest.raises(InterfaceContractError, match="message_id"):
        message(message_id="../forged")


def test_interface_ai_clarification_answer_must_contain_text():
    with pytest.raises(InterfaceContractError, match="requires body.text"):
        message(message_type=MessageType.CLARIFICATION_ANSWER, body={"unexpected": True})


def test_need_rejects_non_boolean_progress_flag():
    with pytest.raises(InterfaceContractError, match="blocks_progress"):
        FactoryNeed(
            need_id="need-002",
            project_key="tradix",
            category=NeedCategory.RESOURCE,
            question="Need compute.",
            reason="Build exceeds current limits.",
            blocks_progress="yes",
        )


def test_user_input_requires_text():
    with pytest.raises(InterfaceContractError, match="requires body.text"):
        message(sender=Sender.USER, message_type=MessageType.USER_INPUT, body={"unexpected": True})


def test_message_rejects_non_iso_timestamp():
    with pytest.raises(InterfaceContractError, match="ISO-8601"):
        message(created_at="yesterday")


def test_factory_need_preserves_specific_unknown_field_error():
    with pytest.raises(InterfaceContractError, match="unknown factory need fields"):
        FactoryNeed.from_mapping({
            "need_id": "need-003",
            "project_key": "tradix",
            "category": "capability",
            "question": "Need a browser.",
            "reason": "No browser adapter is registered.",
            "unexpected": True,
        })


def test_factory_need_project_must_match_message_project():
    with pytest.raises(InterfaceContractError, match="scope must match"):
        message(
            sender=Sender.FACTORY,
            message_type=MessageType.FACTORY_NEED,
            body={
                "need_id": "need-004",
                "project_key": "other-product",
                "category": "capability",
                "question": "Need a browser.",
                "reason": "No browser adapter is registered.",
            },
        )


def test_message_rejects_timestamp_without_timezone():
    with pytest.raises(InterfaceContractError, match="timezone-aware"):
        message(created_at="2026-11-17T19:00:00")



def test_message_body_is_deeply_immutable_after_validation():
    payload = {
        "text": "Create a bounded product mission.",
        "metadata": {"labels": ["reviewed"]},
    }
    item = message(body=payload)

    payload["text"] = "tampered"
    payload["metadata"]["labels"].append("injected")

    assert item.body["text"] == "Create a bounded product mission."
    assert item.body["metadata"]["labels"] == ("reviewed",)
    assert json.loads(json.dumps(item.body)) == {
        "text": "Create a bounded product mission.",
        "metadata": {"labels": ["reviewed"]},
    }
    with pytest.raises(TypeError):
        item.body["text"] = "tampered"
    with pytest.raises(TypeError):
        item.body["metadata"]["new"] = "value"
    with pytest.raises(AttributeError):
        item.body["metadata"]["labels"].append("injected")


def test_message_rejects_non_json_payload_values():
    with pytest.raises(InterfaceContractError, match="JSON-compatible"):
        message(body={"text": "valid text", "unsafe": object()})


def test_message_rejects_non_finite_json_numbers():
    with pytest.raises(InterfaceContractError, match="non-finite"):
        message(body={"text": "valid text", "score": float("nan")})


def test_message_rejects_non_string_json_object_keys():
    with pytest.raises(InterfaceContractError, match="keys must be strings"):
        message(body={"text": "valid text", 7: "invalid key"})


def test_message_rejects_excessively_nested_payloads():
    nested = {"value": "deep"}
    for _ in range(34):
        nested = {"child": nested}
    with pytest.raises(InterfaceContractError, match="maximum nesting depth"):
        message(body={"text": "valid text", "metadata": nested})
