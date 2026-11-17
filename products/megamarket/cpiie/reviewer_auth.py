"""Fail-closed reviewer authentication and authority contract.

Production adapters must validate a signed assertion (for example, an OIDC/JWT
assertion) against a pinned issuer/key set, audience, expiry, revocation policy
and exact company/capability/decision scope. This module deliberately does not
pretend that a reviewer name or local ID is authentication.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol


class ReviewerAuthenticationError(ValueError):
    """Raised when reviewer identity or authority cannot be established."""


@dataclass(frozen=True)
class VerifiedReviewer:
    issuer: str
    subject: str
    key_id: str
    assertion_id: str
    company_id: str
    roles: tuple[str, ...]
    capabilities: tuple[str, ...]
    decisions: tuple[str, ...]
    context_hash: str
    authenticated_at: str
    expires_at: str
    receipt: str


class ReviewerVerifier(Protocol):
    """Trusted adapter boundary; implementations must perform cryptographic checks."""

    def verify_assertion(self, assertion: str) -> VerifiedReviewer:
        """Verify signature, issuer, audience, time, revocation and signed claims."""
        ...

    def verify_receipt(self, receipt: str) -> VerifiedReviewer | None:
        """Re-verify the durable signed authorization receipt at decision time."""
        ...


def _timestamp(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ReviewerAuthenticationError(f"reviewer {field} must be timezone-aware ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReviewerAuthenticationError(f"reviewer {field} must include a timezone offset")
    return parsed.astimezone(timezone.utc)


def authorize_review(
    verifier: ReviewerVerifier | None,
    assertion: str,
    *,
    company_id: str,
    capability: str,
    decision: str,
    context_hash: str,
    now: datetime | None = None,
) -> VerifiedReviewer:
    if verifier is None:
        raise ReviewerAuthenticationError(
            "no trusted reviewer identity verifier is configured; review is blocked"
        )
    if not isinstance(assertion, str) or not assertion.strip():
        raise ReviewerAuthenticationError("a signed reviewer assertion is required")
    try:
        reviewer = verifier.verify_assertion(assertion)
    except Exception as exc:
        raise ReviewerAuthenticationError("reviewer assertion could not be verified") from exc
    if not isinstance(reviewer, VerifiedReviewer):
        raise ReviewerAuthenticationError("reviewer verifier returned an invalid identity")
    required = (
        reviewer.issuer, reviewer.subject, reviewer.key_id, reviewer.assertion_id,
        reviewer.company_id, reviewer.receipt, reviewer.context_hash,
    )
    if not all(isinstance(value, str) and value.strip() for value in required):
        raise ReviewerAuthenticationError("reviewer identity receipt is incomplete")
    if reviewer.company_id != company_id:
        raise ReviewerAuthenticationError("reviewer is not authorized for this company")
    if "policy_reviewer" not in reviewer.roles:
        raise ReviewerAuthenticationError("reviewer lacks the policy_reviewer role")
    if capability not in reviewer.capabilities:
        raise ReviewerAuthenticationError("reviewer is not authorized for this capability")
    if decision not in reviewer.decisions:
        raise ReviewerAuthenticationError("reviewer is not authorized for this decision")
    if reviewer.context_hash != context_hash:
        raise ReviewerAuthenticationError("reviewer assertion is not bound to this exact policy evidence context")
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    authenticated_at = _timestamp(reviewer.authenticated_at, "authenticated_at")
    expires_at = _timestamp(reviewer.expires_at, "expires_at")
    if authenticated_at > current:
        raise ReviewerAuthenticationError("reviewer authentication time is in the future")
    if expires_at <= current:
        raise ReviewerAuthenticationError("reviewer authorization has expired")
    return reviewer


def verify_review_receipt(
    verifier: ReviewerVerifier | None,
    receipt: str | None,
    *,
    issuer: str | None,
    subject: str | None,
    key_id: str | None,
    assertion_id: str | None,
    company_id: str,
    capability: str,
    decision: str,
    context_hash: str,
    now: datetime,
) -> bool:
    if verifier is None or not receipt:
        return False
    try:
        reviewer = verifier.verify_receipt(receipt)
        if not isinstance(reviewer, VerifiedReviewer):
            return False
        if (
            reviewer.issuer != issuer
            or reviewer.subject != subject
            or reviewer.key_id != key_id
            or reviewer.assertion_id != assertion_id
            or reviewer.company_id != company_id
            or "policy_reviewer" not in reviewer.roles
            or capability not in reviewer.capabilities
            or decision not in reviewer.decisions
            or reviewer.context_hash != context_hash
        ):
            return False
        return (
            _timestamp(reviewer.authenticated_at, "authenticated_at") <= now
            and _timestamp(reviewer.expires_at, "expires_at") > now
        )
    except Exception:
        return False
