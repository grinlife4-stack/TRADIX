"""Provider-neutral contracts for the conversational AI <-> TRADIX boundary.

The interface AI translates natural language into bounded proposals and relays
factory needs. It is not the authority for approvals, policy, or execution.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Any, Mapping


_PROJECT_KEY = re.compile(r"^[a-z][a-z0-9-]{1,39}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$")


class InterfaceContractError(ValueError):
    """Raised when an interface message or factory need is invalid."""


class Sender(str, Enum):
    USER = "user"
    INTERFACE_AI = "interface_ai"
    FACTORY = "factory"


class MessageType(str, Enum):
    USER_INPUT = "user_input"
    MISSION_PROPOSAL = "mission_proposal"
    STATUS_QUERY = "status_query"
    CAPABILITY_QUERY = "capability_query"
    CLARIFICATION_ANSWER = "clarification_answer"
    FACTORY_NEED = "factory_need"
    STATUS_UPDATE = "status_update"
    RESULT = "result"
    BLOCKED = "blocked"


_ALLOWED_TYPES = {
    Sender.USER: {MessageType.USER_INPUT},
    Sender.INTERFACE_AI: {
        MessageType.MISSION_PROPOSAL,
        MessageType.STATUS_QUERY,
        MessageType.CAPABILITY_QUERY,
        MessageType.CLARIFICATION_ANSWER,
    },
    Sender.FACTORY: {
        MessageType.FACTORY_NEED,
        MessageType.STATUS_UPDATE,
        MessageType.RESULT,
        MessageType.BLOCKED,
    },
}


def _required_text(name: str, value: Any, maximum: int = 12000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise InterfaceContractError(f"{name} must contain 1..{maximum} characters")
    return value


def _identifier(name: str, value: Any) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise InterfaceContractError(f"{name} must be a valid identifier")
    return value


@dataclass(frozen=True, slots=True)
class InterfaceMessage:
    """A single auditable message crossing the conversational interface boundary."""

    message_id: str
    conversation_id: str
    project_key: str
    correlation_id: str
    sender: Sender
    message_type: MessageType
    body: Mapping[str, Any]
    created_at: str
    reply_to: str | None = None

    def __post_init__(self) -> None:
        _identifier("message_id", self.message_id)
        _identifier("conversation_id", self.conversation_id)
        _identifier("correlation_id", self.correlation_id)
        if not isinstance(self.project_key, str) or not _PROJECT_KEY.fullmatch(self.project_key):
            raise InterfaceContractError("project_key must be a lowercase slug (2..40 characters)")
        if not isinstance(self.sender, Sender) or not isinstance(self.message_type, MessageType):
            raise InterfaceContractError("sender and message_type must use their defined enums")
        if self.message_type not in _ALLOWED_TYPES[self.sender]:
            raise InterfaceContractError("message_type is not permitted for this sender")
        if not isinstance(self.body, Mapping) or not self.body:
            raise InterfaceContractError("body must be a non-empty object")
        if not isinstance(self.created_at, str) or not self.created_at.strip() or len(self.created_at) > 40:
            raise InterfaceContractError("created_at must be a non-empty timestamp string")
        if self.reply_to is not None:
            _identifier("reply_to", self.reply_to)

        if self.message_type in (MessageType.MISSION_PROPOSAL, MessageType.CLARIFICATION_ANSWER):
            if "text" not in self.body:
                raise InterfaceContractError("this message type requires body.text")
            _required_text("body.text", self.body["text"])
        elif self.message_type in (MessageType.STATUS_QUERY, MessageType.CAPABILITY_QUERY):
            if "query" not in self.body:
                raise InterfaceContractError("query message requires body.query")
            _required_text("body.query", self.body["query"], 2000)
        elif self.message_type is MessageType.FACTORY_NEED:
            FactoryNeed.from_mapping(self.body)
        elif self.message_type in (MessageType.STATUS_UPDATE, MessageType.RESULT, MessageType.BLOCKED):
            if "summary" not in self.body:
                raise InterfaceContractError("factory response requires body.summary")
            _required_text("body.summary", self.body["summary"])


class NeedCategory(str, Enum):
    MISSING_INFORMATION = "missing_information"
    CAPABILITY = "capability"
    RESOURCE = "resource"
    POLICY_DECISION = "policy_decision"
    RESERVED_APPROVAL = "reserved_approval"
    BLOCKED_DEPENDENCY = "blocked_dependency"


class NeedPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class FactoryNeed:
    """A structured request from the factory; it never grants authority by itself."""

    need_id: str
    project_key: str
    category: NeedCategory
    question: str
    reason: str
    priority: NeedPriority = NeedPriority.NORMAL
    blocks_progress: bool = True
    mission_id: str | None = None

    def __post_init__(self) -> None:
        _identifier("need_id", self.need_id)
        if not isinstance(self.project_key, str) or not _PROJECT_KEY.fullmatch(self.project_key):
            raise InterfaceContractError("project_key must be a lowercase slug (2..40 characters)")
        if not isinstance(self.category, NeedCategory):
            raise InterfaceContractError("category must be a NeedCategory value")
        if not isinstance(self.priority, NeedPriority):
            raise InterfaceContractError("priority must be a NeedPriority value")
        _required_text("question", self.question, 4000)
        _required_text("reason", self.reason, 4000)
        if not isinstance(self.blocks_progress, bool):
            raise InterfaceContractError("blocks_progress must be a boolean")
        if self.mission_id is not None:
            _identifier("mission_id", self.mission_id)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "FactoryNeed":
        if not isinstance(value, Mapping):
            raise InterfaceContractError("factory need must be an object")
        required = {"need_id", "project_key", "category", "question", "reason"}
        optional = {"priority", "blocks_progress", "mission_id"}
        unknown = set(value) - required - optional
        missing = required - set(value)
        if unknown:
            raise InterfaceContractError(f"unknown factory need fields: {', '.join(sorted(unknown))}")
        if missing:
            raise InterfaceContractError(f"missing factory need fields: {', '.join(sorted(missing))}")
        try:
            return cls(
                need_id=value["need_id"],
                project_key=value["project_key"],
                category=NeedCategory(value["category"]),
                question=value["question"],
                reason=value["reason"],
                priority=NeedPriority(value.get("priority", NeedPriority.NORMAL.value)),
                blocks_progress=value.get("blocks_progress", True),
                mission_id=value.get("mission_id"),
            )
        except (TypeError, ValueError) as exc:
            if isinstance(exc, InterfaceContractError):
                raise
            raise InterfaceContractError("factory need contains an invalid enum or field value") from exc
