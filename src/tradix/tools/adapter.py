"""Vendor-neutral, non-shell tool adapter contract.

This module defines validated requests and results only. It does not execute tools.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable
from urllib.parse import urlparse

_HEX_SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_JOB_TYPE_RE = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+){1,5}$")
_HEALTH = {"healthy", "degraded", "unavailable", "unknown"}
_RESULT = {"succeeded", "failed", "blocked", "cancelled"}
_EVIDENCE_SCHEMES = {"https", "evidence"}


class AdapterContractError(ValueError):
    """Raised when an adapter request or response violates the contract."""


@dataclass(frozen=True)
class ResourceLimits:
    cpu_millis: int = 1000
    memory_mb: int = 512
    timeout_seconds: int = 300
    network_enabled: bool = False
    writable_workspace: bool = False

    def validate(self) -> None:
        if type(self.cpu_millis) is not int or not 100 <= self.cpu_millis <= 32000:
            raise AdapterContractError("cpu_millis must be an integer from 100 to 32000")
        if type(self.memory_mb) is not int or not 64 <= self.memory_mb <= 32768:
            raise AdapterContractError("memory_mb must be an integer from 64 to 32768")
        if type(self.timeout_seconds) is not int or not 1 <= self.timeout_seconds <= 3600:
            raise AdapterContractError("timeout_seconds must be an integer from 1 to 3600")
        if type(self.network_enabled) is not bool or type(self.writable_workspace) is not bool:
            raise AdapterContractError("resource permission flags must be booleans")


@dataclass(frozen=True)
class ToolInvocation:
    run_id: str
    tool_id: str
    tool_version: str
    job_type: str
    source_commit_sha: str
    input_refs: tuple[str, ...]
    idempotency_key: str
    limits: ResourceLimits = ResourceLimits()

    def validate(self, supported_job_types: tuple[str, ...]) -> None:
        if not isinstance(self.run_id, str) or not _RUN_ID_RE.fullmatch(self.run_id):
            raise AdapterContractError("run_id has invalid format")
        if not isinstance(self.tool_id, str) or not self.tool_id.strip():
            raise AdapterContractError("tool_id is required")
        if not isinstance(self.tool_version, str) or not self.tool_version.strip():
            raise AdapterContractError("tool_version is required")
        if not isinstance(self.job_type, str) or not _JOB_TYPE_RE.fullmatch(self.job_type):
            raise AdapterContractError("job_type has invalid format")
        if self.job_type not in supported_job_types:
            raise AdapterContractError("job_type is not allowlisted by this adapter")
        if not isinstance(self.source_commit_sha, str) or not _HEX_SHA_RE.fullmatch(self.source_commit_sha):
            raise AdapterContractError("source_commit_sha must be a full hexadecimal Git SHA")
        if not isinstance(self.input_refs, tuple) or not self.input_refs or len(self.input_refs) > 32:
            raise AdapterContractError("input_refs must contain 1 to 32 references")
        for ref in self.input_refs:
            parsed = urlparse(ref) if isinstance(ref, str) else None
            if parsed is None or parsed.scheme not in _EVIDENCE_SCHEMES or not parsed.netloc:
                raise AdapterContractError("input references must use https:// or evidence://")
            if parsed.username is not None or parsed.password is not None:
                raise AdapterContractError("input references must not contain embedded credentials")
        if not isinstance(self.idempotency_key, str) or not _RUN_ID_RE.fullmatch(self.idempotency_key):
            raise AdapterContractError("idempotency_key has invalid format")
        if not isinstance(self.limits, ResourceLimits):
            raise AdapterContractError("limits must be ResourceLimits")
        self.limits.validate()


@dataclass(frozen=True)
class AdapterHealth:
    status: Literal["healthy", "degraded", "unavailable", "unknown"]
    checked_at: str
    adapter_version: str
    detail: str = ""

    def validate(self) -> None:
        if self.status not in _HEALTH:
            raise AdapterContractError("unknown adapter health status")
        if not isinstance(self.checked_at, str) or not self.checked_at.strip():
            raise AdapterContractError("checked_at is required")
        if not isinstance(self.adapter_version, str) or not self.adapter_version.strip():
            raise AdapterContractError("adapter_version is required")
        if not isinstance(self.detail, str) or len(self.detail) > 2000:
            raise AdapterContractError("detail must be a string of at most 2000 characters")


@dataclass(frozen=True)
class AdapterResult:
    run_id: str
    status: Literal["succeeded", "failed", "blocked", "cancelled"]
    started_at: str
    finished_at: str
    source_commit_sha: str
    output_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    error_code: str = ""
    error_message: str = ""

    def validate(self, invocation: ToolInvocation) -> None:
        if self.run_id != invocation.run_id:
            raise AdapterContractError("result run_id does not match invocation")
        if self.status not in _RESULT:
            raise AdapterContractError("unknown adapter result status")
        if self.source_commit_sha != invocation.source_commit_sha:
            raise AdapterContractError("result source SHA does not match invocation")
        for name, value in (("started_at", self.started_at), ("finished_at", self.finished_at)):
            if not isinstance(value, str) or not value.strip():
                raise AdapterContractError(f"{name} is required")
        for name, refs in (("output_refs", self.output_refs), ("evidence_refs", self.evidence_refs)):
            if not isinstance(refs, tuple) or len(refs) > 128:
                raise AdapterContractError(f"{name} must be a tuple with at most 128 references")
            for ref in refs:
                parsed = urlparse(ref) if isinstance(ref, str) else None
                if parsed is None or parsed.scheme not in _EVIDENCE_SCHEMES or not parsed.netloc:
                    raise AdapterContractError(f"{name} contains an invalid reference")
                if parsed.username is not None or parsed.password is not None:
                    raise AdapterContractError(f"{name} must not contain embedded credentials")
        if self.status == "succeeded" and not self.evidence_refs:
            raise AdapterContractError("successful results require evidence references")
        if self.status == "failed" and not self.error_code:
            raise AdapterContractError("failed results require a normalized error_code")
        if not isinstance(self.error_message, str) or len(self.error_message) > 2000:
            raise AdapterContractError("error_message must be a string of at most 2000 characters")


@runtime_checkable
class ToolAdapter(Protocol):
    """An adapter exposes bounded jobs; it must not accept arbitrary shell commands."""

    tool_id: str
    tool_version: str
    adapter_version: str
    supported_job_types: tuple[str, ...]

    def health_check(self) -> AdapterHealth: ...
    def execute(self, invocation: ToolInvocation) -> AdapterResult: ...
    def cancel(self, run_id: str) -> bool: ...
    def collect_logs(self, run_id: str) -> tuple[str, ...]: ...


def validate_adapter(adapter: ToolAdapter) -> None:
    required = ("tool_id", "tool_version", "adapter_version", "supported_job_types",
                "health_check", "execute", "cancel", "collect_logs")
    for name in required:
        if not hasattr(adapter, name):
            raise AdapterContractError(f"adapter is missing {name}")
    if not isinstance(adapter.tool_id, str) or not adapter.tool_id.strip():
        raise AdapterContractError("adapter tool_id is required")
    if not isinstance(adapter.tool_version, str) or not adapter.tool_version.strip():
        raise AdapterContractError("adapter tool_version is required")
    if not isinstance(adapter.adapter_version, str) or not adapter.adapter_version.strip():
        raise AdapterContractError("adapter_version is required")
    if not isinstance(adapter.supported_job_types, tuple) or not adapter.supported_job_types:
        raise AdapterContractError("supported_job_types must be a non-empty tuple")
    if len(set(adapter.supported_job_types)) != len(adapter.supported_job_types):
        raise AdapterContractError("supported_job_types must be unique")
    if any(not isinstance(item, str) or not _JOB_TYPE_RE.fullmatch(item)
           for item in adapter.supported_job_types):
        raise AdapterContractError("supported_job_types contains an invalid job type")
