"""Typed adapter contract and budget guard for ECOSCAN scans."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from .models import ScanBudget, SourceDescriptor


class BudgetExceeded(RuntimeError):
    """Raised by an adapter when an explicit scan budget is exhausted."""


class AdapterContractError(ValueError):
    """Raised when an adapter result violates the ECOSCAN contract."""


class BudgetGuard:
    def __init__(self, budget: ScanBudget) -> None:
        self.budget = budget
        self.started = time.monotonic()
        self.deadline = self.started + budget.max_duration_seconds
        self.items_seen = 0
        self.pages_seen = 0

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, self.deadline - time.monotonic())

    def check_time(self) -> None:
        if time.monotonic() >= self.deadline:
            raise BudgetExceeded("max_duration_seconds exhausted")

    def consume_item(self) -> None:
        self.check_time()
        if self.items_seen >= self.budget.max_items:
            raise BudgetExceeded("max_items exhausted")
        self.items_seen += 1

    def consume_page(self) -> None:
        self.check_time()
        if self.pages_seen >= self.budget.max_pages:
            raise BudgetExceeded("max_pages exhausted")
        self.pages_seen += 1


@dataclass(frozen=True, slots=True)
class ScanContext:
    project_id: str
    actor_id: str
    source: SourceDescriptor
    budget: ScanBudget
    guard: BudgetGuard
    checkpoint: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class AdapterResult:
    coverage_state: str
    measurements: tuple[Mapping[str, Any], ...]
    items_seen: int
    pages_seen: int
    reason_code: str | None = None
    limitations: tuple[str, ...] = ()
    checkpoint: Mapping[str, Any] | None = None


class Adapter(Protocol):
    adapter_id: str
    version: str

    def validate_config(self, source: SourceDescriptor) -> None:
        """Validate only local adapter configuration; must not perform a scan."""

    def scan(self, context: ScanContext) -> AdapterResult:
        """Perform one bounded read-only scan and report exact observed coverage."""
