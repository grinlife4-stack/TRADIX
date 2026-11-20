"""Default-deny project, subsystem, source, and owner/operator gates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .models import ProjectRegistry, SourceDescriptor


Authorizer = Callable[[str, str, str, str, str], bool]


@dataclass(frozen=True, slots=True)
class ControlState:
    global_enabled: bool = False
    enabled_projects: frozenset[str] = frozenset()
    enabled_subsystems: frozenset[tuple[str, str]] = frozenset()
    enabled_sources: frozenset[tuple[str, str]] = frozenset()

    def __post_init__(self) -> None:
        if type(self.global_enabled) is not bool:
            raise ValueError("global_enabled must be a boolean")
        object.__setattr__(self, "enabled_projects", frozenset(self.enabled_projects))
        object.__setattr__(self, "enabled_subsystems", frozenset(self.enabled_subsystems))
        object.__setattr__(self, "enabled_sources", frozenset(self.enabled_sources))


@dataclass(frozen=True, slots=True)
class GateDecision:
    allowed: bool
    coverage_state: str | None
    reason_code: str | None


class ExecutionGate:
    """Evaluate all controls immediately before a source operation.

    The authorizer receives actor_id, project_id, owner_id, operator_id, and source_id.
    No authorizer means deny. A control toggle never grants owner/operator authority.
    """

    def __init__(self, controls: ControlState, authorizer: Authorizer | None = None) -> None:
        self._controls = controls
        self._authorizer = authorizer

    def evaluate(
        self,
        registry: ProjectRegistry,
        source: SourceDescriptor,
        actor_id: str,
    ) -> GateDecision:
        project_id = registry.project_id
        if not self._controls.global_enabled:
            return GateDecision(False, "DISABLED", "global_disabled")
        if project_id not in self._controls.enabled_projects:
            return GateDecision(False, "DISABLED", "project_disabled")
        if (project_id, source.subsystem_id) not in self._controls.enabled_subsystems:
            return GateDecision(False, "DISABLED", "subsystem_disabled")
        if not source.enabled or (project_id, source.source_id) not in self._controls.enabled_sources:
            return GateDecision(False, "DISABLED", "source_disabled")
        if self._authorizer is None:
            return GateDecision(False, "NOT_AUTHORIZED", "owner_operator_authorization_missing")
        try:
            authorized = self._authorizer(
                actor_id, project_id, source.owner_id, source.operator_id, source.source_id
            )
        except Exception:
            authorized = False
        if authorized is not True:
            return GateDecision(False, "NOT_AUTHORIZED", "owner_operator_authorization_missing")
        return GateDecision(True, None, None)
