"""Typed, dependency-free ECOSCAN 0.1 data models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScanBudget:
    max_pages: int
    max_items: int
    timeout_seconds: int
    max_duration_seconds: int


@dataclass(frozen=True, slots=True)
class RetentionPolicy:
    history_days: int
    evidence_days: int


@dataclass(frozen=True, slots=True)
class SourceDescriptor:
    source_id: str
    owner_id: str
    operator_id: str
    subsystem_id: str
    source_type: str
    locator: str
    adapter_id: str
    adapter_version: str
    credential_ref: str | None
    enabled: bool
    scope_tags: tuple[str, ...]
    budget: ScanBudget
    expected_measurements: tuple[str, ...]
    retention_policy: RetentionPolicy
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class ProjectRegistry:
    schema_version: str
    project_id: str
    sources: tuple[SourceDescriptor, ...]
