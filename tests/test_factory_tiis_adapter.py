from datetime import datetime, timezone

import pytest

from tradix.factory.interface_contract import InterfaceMessage, MessageType, Sender
from tradix.factory.tiis_adapter import (
    DOMAIN_CONTRACT_ID,
    FactoryTIISAdapterError,
    from_tiis_envelope,
    to_tiis_envelope,
)
from tradix.tiis import TIISAuthorizationError, TIISValidator


SENDER_COMPONENT = {"project_id": "tradix", "component_id": "interface-gateway"}
FACTORY_COMPONENT = {"project_id": "tradix", "component_id": "factory-runtime"}
NOW = datetime(2026, 11, 17, 19, 0, 10, tzinfo=timezone.utc)


def mission_proposal() -> InterfaceMessage:
    return InterfaceMessage(
        message_id="msg-001",
        conversation_id="conv-001",
        project_key="nexora",
        correlation_id="mission-001",
        sender=Sender.INTERFACE_AI,
        message_type=MessageType.MISSION_PROPOSAL,
        body={"text": "Create a bounded product mission.", "metadata": {"labels": ["review"]}},
        created_at="2026-11-17T19:00:00Z",
    )


def factory_need() -> InterfaceMessage:
    return InterfaceMessage(
        message_id="need-msg-001",
        conversation_id="conv-001",
        project_key="nexora",
        correlation_id="mission-001",
        sender=Sender.FACTORY,
        message_type=MessageType.FACTORY_NEED,
        body={
            "need_id": "need-001",
            "project_key": "nexora",
            "category": "missing_information",
            "question": "Which operating jurisdiction applies?",
            "reason": "Compliance rules depend on jurisdiction.",
            "priority": "high",
            "blocks_progress": True,
        },
        created_at="2026-11-17T19:00:00Z",
    )


def validator() -> TIISValidator:
    return TIISValidator(authorization_policy=lambda *_args: True)


def test_mission_proposal_is_wrapped_as_tiis_request_without_confusing_actor_and_component() -> None:
    envelope = to_tiis_envelope(
        mission_proposal(),
        sender_component=SENDER_COMPONENT,
        recipient_component=FACTORY_COMPONENT,
    )
    assert envelope["message_type"] == "request"
    assert envelope["operation"] == "mission-proposal"
    assert envelope["sender"] == SENDER_COMPONENT
    assert envelope["payload"]["contract_id"] == DOMAIN_CONTRACT_ID
    assert envelope["payload"]["message"]["sender"] == "interface_ai"
    assert envelope["message_id"] == to_tiis_envelope(
        mission_proposal(),
        sender_component=SENDER_COMPONENT,
        recipient_component=FACTORY_COMPONENT,
    )["message_id"]


def test_factory_need_is_wrapped_as_tiis_event() -> None:
    envelope = to_tiis_envelope(
        factory_need(),
        sender_component=FACTORY_COMPONENT,
        recipient_component=SENDER_COMPONENT,
    )
    assert envelope["message_type"] == "event"
    assert envelope["event_type"] == "factory.factory-need"
    assert envelope["payload"]["message"]["sender"] == "factory"


def test_tiis_round_trip_revalidates_domain_contract_and_project_scope() -> None:
    original = mission_proposal()
    envelope = to_tiis_envelope(
        original,
        sender_component=SENDER_COMPONENT,
        recipient_component=FACTORY_COMPONENT,
    )
    restored = from_tiis_envelope(
        envelope,
        validator=validator(),
        authenticated_sender=SENDER_COMPONENT,
        expected_recipient=FACTORY_COMPONENT,
        project_authorizer=lambda item: item.project_key == "nexora",
        now=NOW,
    )
    assert restored.message_id == original.message_id
    assert restored.project_key == original.project_key
    assert restored.sender is Sender.INTERFACE_AI
    assert restored.body["metadata"]["labels"] == ("review",)


def test_project_scope_authorization_is_separate_and_fail_closed() -> None:
    envelope = to_tiis_envelope(
        mission_proposal(),
        sender_component=SENDER_COMPONENT,
        recipient_component=FACTORY_COMPONENT,
    )
    with pytest.raises(TIISAuthorizationError, match="factory_project_scope_not_authorized"):
        from_tiis_envelope(
            envelope,
            validator=validator(),
            authenticated_sender=SENDER_COMPONENT,
            expected_recipient=FACTORY_COMPONENT,
            project_authorizer=lambda _item: False,
            now=NOW,
        )
    with pytest.raises(TIISAuthorizationError, match="factory_project_policy_not_configured"):
        from_tiis_envelope(
            envelope,
            validator=validator(),
            authenticated_sender=SENDER_COMPONENT,
            expected_recipient=FACTORY_COMPONENT,
            project_authorizer=None,
            now=NOW,
        )


def test_outer_component_identity_cannot_be_forged_by_domain_actor() -> None:
    envelope = to_tiis_envelope(
        mission_proposal(),
        sender_component=SENDER_COMPONENT,
        recipient_component=FACTORY_COMPONENT,
    )
    with pytest.raises(TIISAuthorizationError, match="authenticated_sender_mismatch"):
        from_tiis_envelope(
            envelope,
            validator=validator(),
            authenticated_sender={"project_id": "tradix", "component_id": "other-service"},
            expected_recipient=FACTORY_COMPONENT,
            project_authorizer=lambda _item: True,
            now=NOW,
        )


def test_mismatched_domain_and_outer_operation_is_rejected() -> None:
    envelope = to_tiis_envelope(
        mission_proposal(),
        sender_component=SENDER_COMPONENT,
        recipient_component=FACTORY_COMPONENT,
    )
    envelope["operation"] = "status-query"
    with pytest.raises(FactoryTIISAdapterError, match="domain_and_tiis_operation_disagree"):
        from_tiis_envelope(
            envelope,
            validator=validator(),
            authenticated_sender=SENDER_COMPONENT,
            expected_recipient=FACTORY_COMPONENT,
            project_authorizer=lambda _item: True,
            now=NOW,
        )


def test_invalid_factory_domain_payload_is_rejected() -> None:
    envelope = to_tiis_envelope(
        mission_proposal(),
        sender_component=SENDER_COMPONENT,
        recipient_component=FACTORY_COMPONENT,
    )
    envelope["payload"]["message"]["message_type"] = "result"
    with pytest.raises(FactoryTIISAdapterError, match="factory_domain_message_rejected"):
        from_tiis_envelope(
            envelope,
            validator=validator(),
            authenticated_sender=SENDER_COMPONENT,
            expected_recipient=FACTORY_COMPONENT,
            project_authorizer=lambda _item: True,
            now=NOW,
        )


def test_ttl_is_bounded() -> None:
    with pytest.raises(ValueError, match="ttl_seconds"):
        to_tiis_envelope(
            mission_proposal(),
            sender_component=SENDER_COMPONENT,
            recipient_component=FACTORY_COMPONENT,
            ttl_seconds=0,
        )
