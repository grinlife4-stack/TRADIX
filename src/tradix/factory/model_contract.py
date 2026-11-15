"""Provider-neutral model contracts and validated, non-executable plans.

No SDK, network access, credentials, or tool execution lives in this module.
Model output is untrusted data and must pass validation before downstream use.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Protocol


class ModelContractError(ValueError):
    """Raised when a model request, response, or plan is malformed."""


@dataclass(frozen=True, slots=True)
class ModelRequest:
    task_id: str
    purpose: str
    instructions: str
    input_text: str
    model_id: str
    timeout_seconds: int = 60
    max_output_tokens: int = 2000

    def __post_init__(self) -> None:
        fields = (self.task_id, self.purpose, self.instructions, self.input_text, self.model_id)
        if any(not isinstance(value, str) or not value.strip() for value in fields):
            raise ModelContractError("request text fields must be non-empty strings")
        if len(self.input_text) > 20000 or len(self.instructions) > 12000:
            raise ModelContractError("model request exceeds text limits")
        if isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, int) or not 1 <= self.timeout_seconds <= 300:
            raise ModelContractError("timeout_seconds must be an integer from 1 to 300")
        if isinstance(self.max_output_tokens, bool) or not isinstance(self.max_output_tokens, int) or not 1 <= self.max_output_tokens <= 16000:
            raise ModelContractError("max_output_tokens must be an integer from 1 to 16000")


@dataclass(frozen=True, slots=True)
class ModelResponse:
    provider: str
    model_id: str
    output_text: str
    request_id: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    finish_reason: str = "stop"

    def __post_init__(self) -> None:
        for name, value in (
            ("provider", self.provider),
            ("model_id", self.model_id),
            ("output_text", self.output_text),
            ("request_id", self.request_id),
            ("finish_reason", self.finish_reason),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ModelContractError(f"{name} must be a non-empty string")
        if len(self.output_text) > 100000:
            raise ModelContractError("output_text exceeds 100000 characters")
        for name, value in (("input_tokens", self.input_tokens), ("output_tokens", self.output_tokens)):
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise ModelContractError(f"{name} must be a non-negative integer or None")


class ModelAdapter(Protocol):
    """Provider implementation boundary; implementations must not execute model output."""

    def generate(self, request: ModelRequest) -> ModelResponse:
        """Return raw text and provider metadata; caller validates all content."""


@dataclass(frozen=True, slots=True)
class PlanStep:
    step_id: str
    action: str
    rationale: str
    acceptance_check: str

    def __post_init__(self) -> None:
        values = (self.step_id, self.action, self.rationale, self.acceptance_check)
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ModelContractError("all plan step fields must be non-empty strings")
        if any(len(value) > 1000 for value in values):
            raise ModelContractError("plan step field exceeds 1000 characters")


@dataclass(frozen=True, slots=True)
class PlanDocument:
    summary: str
    steps: tuple[PlanStep, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.summary, str) or not self.summary.strip() or len(self.summary) > 2000:
            raise ModelContractError("plan summary must contain 1..2000 characters")
        if not isinstance(self.steps, tuple) or not 1 <= len(self.steps) <= 20:
            raise ModelContractError("plan must contain 1..20 steps")
        if any(not isinstance(step, PlanStep) for step in self.steps):
            raise ModelContractError("steps must contain PlanStep values")
        ids = [step.step_id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ModelContractError("plan step IDs must be unique")

    @classmethod
    def from_model_response(cls, response: ModelResponse) -> "PlanDocument":
        if not isinstance(response, ModelResponse):
            raise ModelContractError("response must be a validated ModelResponse")
        try:
            payload = json.loads(response.output_text)
        except json.JSONDecodeError as exc:
            raise ModelContractError("model output must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise ModelContractError("model plan must be a JSON object")
        if set(payload) != {"summary", "steps"}:
            raise ModelContractError("model plan must contain exactly summary and steps")
        if not isinstance(payload["summary"], str) or not isinstance(payload["steps"], list):
            raise ModelContractError("summary must be text and steps must be an array")
        parsed_steps = []
        for item in payload["steps"]:
            if not isinstance(item, dict) or set(item) != {
                "step_id", "action", "rationale", "acceptance_check"
            }:
                raise ModelContractError("each plan step must contain exactly the four documented fields")
            if any(not isinstance(item[key], str) for key in item):
                raise ModelContractError("all plan step values must be strings")
            parsed_steps.append(PlanStep(**item))
        return cls(summary=payload["summary"], steps=tuple(parsed_steps))
