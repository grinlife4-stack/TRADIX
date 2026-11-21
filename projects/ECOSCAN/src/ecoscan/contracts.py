from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Any, Mapping, Protocol
from .models import ScanBudget, SourceDescriptor

class AdapterContractError(ValueError):
    pass

class BudgetExceeded(RuntimeError):
    pass

class TransportOutcomeUnknown(RuntimeError):
    """A remote request may have executed, but no trustworthy outcome was received."""
    pass

class AuthorizationRevoked(RuntimeError):
    pass

@dataclass(frozen=True, slots=True)
class AdapterResult:
    coverage_state: str
    measurements: tuple[dict[str, Any], ...]
    items_seen: int
    pages_seen: int
    reason_code: str | None = None
    limitations: tuple[str, ...] = ()
    checkpoint: Mapping[str, Any] | None = None

class BudgetGuard:
    def __init__(self, budget: ScanBudget, before_page=None) -> None:
        self.budget = budget
        self.before_page = before_page
        self.pages_seen = 0
        self.items_seen = 0
        self.started = time.monotonic()
        self.deadline = self.started + min(
            self.budget.timeout_seconds,
            self.budget.max_duration_seconds,
        )

    def remaining_seconds(self) -> float:
        return max(0.0, self.deadline - time.monotonic())

    def check_deadline(self) -> None:
        if time.monotonic() >= self.deadline:
            raise BudgetExceeded("scan time budget exceeded")

    def _check_time(self) -> None:
        self.check_deadline()

    def consume_page(self) -> None:
        if self.before_page is not None and self.before_page() is not True:
            raise AuthorizationRevoked("authorization was revoked")
        self._check_time()
        if self.pages_seen + 1 > self.budget.max_pages:
            raise BudgetExceeded("page budget exceeded")
        self.pages_seen += 1

    def consume_item(self) -> None:
        self._check_time()
        if self.items_seen + 1 > self.budget.max_items:
            raise BudgetExceeded("item budget exceeded")
        self.items_seen += 1

@dataclass(frozen=True, slots=True)
class ScanContext:
    project_id: str
    actor_id: str
    source: SourceDescriptor
    budget: ScanBudget
    guard: BudgetGuard
    checkpoint: Mapping[str, Any] | None = None
    scan_id: str | None = None
    operation_intent: Mapping[str, Any] | None = None

class Adapter(Protocol):
    adapter_id: str
    version: str
    def validate_config(self, source_descriptor: SourceDescriptor) -> None: ...
    def scan(self, context: ScanContext) -> AdapterResult: ...
