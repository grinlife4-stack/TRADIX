"""Provider-neutral, read-only CPIIE registry for MegaMarket.

This package records official sources, immutable document snapshots, evidence and
reviewed rules. The registry itself performs no network access or external actions.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import StrEnum
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .reviewer_auth import ReviewerVerifier, authorize_review, verify_review_receipt


class RuleState(StrEnum):
    NEEDS_REVIEW = "NEEDS_REVIEW"
    VERIFIED = "VERIFIED"
    CONFLICT = "CONFLICT"
    EXPIRED = "EXPIRED"


class PolicyEffect(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    UNSPECIFIED = "UNSPECIFIED"


class CapabilityState(StrEnum):
    BLOCKED_NO_POLICY = "BLOCKED_NO_POLICY"
    BLOCKED_REVIEW = "BLOCKED_REVIEW"
    BLOCKED_CONFLICT = "BLOCKED_CONFLICT"
    BLOCKED_EXPIRED = "BLOCKED_EXPIRED"
    BLOCKED_POLICY_DENY = "BLOCKED_POLICY_DENY"
    ALLOWED = "ALLOWED"


@dataclass(frozen=True)
class Source:
    source_id: str
    company_id: str
    role: str
    url: str
    title: str


@dataclass(frozen=True)
class Document:
    document_id: str
    source_id: str
    fetched_at: str
    content_sha256: str
    version: int
    changed: bool


@dataclass(frozen=True)
class Rule:
    rule_id: str
    document_id: str
    capability: str
    statement: str
    effect: PolicyEffect
    state: RuleState
    expires_at: str | None


@dataclass(frozen=True)
class Evaluation:
    capability: str
    state: CapabilityState
    rule_ids: tuple[str, ...]
    reason: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_aware_timestamp(value: str, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a timezone-aware ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be a timezone-aware ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone offset")
    return parsed.astimezone(timezone.utc)


def canonicalize_url(url: str) -> str:
    """Accept HTTPS URLs only; normalize host and remove fragments/default port."""
    parts = urlsplit(url.strip())
    if parts.scheme.lower() != "https" or not parts.hostname:
        raise ValueError("official source URL must use HTTPS")
    if parts.username or parts.password:
        raise ValueError("credentials are not allowed in source URLs")
    host = parts.hostname.encode("idna").decode("ascii").lower().rstrip(".")
    if not re.fullmatch(r"[a-z0-9.-]+", host) or "." not in host:
        raise ValueError("source must use a fully qualified public hostname")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("IP-literal source URLs are not allowed")
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal",
                                              ".test", ".invalid", ".onion")):
        raise ValueError("local or reserved source hostname is not allowed")
    port = parts.port
    if port not in (None, 443):
        raise ValueError("only the standard HTTPS port is allowed")
    netloc = host
    path = parts.path or "/"
    return urlunsplit(("https", netloc, path, parts.query, ""))


class CPIIERegistry:
    """SQLite-backed registry. No fetching, scraping, or outbound interaction."""

    def __init__(self, database: str | Path = ":memory:",
                 reviewer_verifier: ReviewerVerifier | None = None) -> None:
        self.reviewer_verifier = reviewer_verifier
        self.connection = sqlite3.connect(str(database))
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._initialize()

    def close(self) -> None:
        self.connection.close()

    def _initialize(self) -> None:
        self.connection.executescript("""
        CREATE TABLE IF NOT EXISTS sources (
            source_id TEXT PRIMARY KEY,
            company_id TEXT NOT NULL,
            role TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TRIGGER IF NOT EXISTS source_identity_immutable
            BEFORE UPDATE OF company_id, role, url ON sources
            WHEN OLD.company_id IS NOT NEW.company_id
              OR OLD.role IS NOT NEW.role
              OR OLD.url IS NOT NEW.url
            BEGIN SELECT RAISE(ABORT, 'source identity is immutable'); END;
        CREATE TABLE IF NOT EXISTS documents (
            document_id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL REFERENCES sources(source_id),
            fetched_at TEXT NOT NULL,
            content_sha256 TEXT NOT NULL,
            content TEXT NOT NULL,
            version INTEGER NOT NULL,
            UNIQUE(source_id, content_sha256)
        );
        CREATE TABLE IF NOT EXISTS evidence (
            evidence_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL REFERENCES documents(document_id),
            locator TEXT NOT NULL,
            excerpt TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rules (
            rule_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL REFERENCES documents(document_id),
            evidence_id TEXT NOT NULL REFERENCES evidence(evidence_id),
            capability TEXT NOT NULL,
            statement TEXT NOT NULL,
            effect TEXT NOT NULL DEFAULT 'UNSPECIFIED' CHECK (effect IN ('ALLOW', 'DENY', 'UNSPECIFIED')),
            state TEXT NOT NULL,
            expires_at TEXT,
            reviewer TEXT,
            reviewed_at TEXT,
            reviewer_issuer TEXT,
            reviewer_subject TEXT,
            reviewer_key_id TEXT,
            reviewer_assertion_id TEXT,
            reviewer_company_id TEXT,
            reviewer_capabilities TEXT,
            reviewer_decisions TEXT,
            reviewer_authenticated_at TEXT,
            reviewer_expires_at TEXT,
            reviewer_receipt TEXT
        );
        CREATE INDEX IF NOT EXISTS rules_capability_idx ON rules(capability);
        CREATE TABLE IF NOT EXISTS rule_review_history (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id TEXT NOT NULL REFERENCES rules(rule_id),
            previous_state TEXT NOT NULL,
            decision TEXT NOT NULL,
            reviewer TEXT NOT NULL,
            reviewed_at TEXT NOT NULL,
            reviewer_issuer TEXT,
            reviewer_subject TEXT,
            reviewer_key_id TEXT,
            reviewer_assertion_id TEXT,
            reviewer_company_id TEXT,
            reviewer_capabilities TEXT,
            reviewer_decisions TEXT,
            reviewer_authenticated_at TEXT,
            reviewer_expires_at TEXT,
            reviewer_receipt TEXT
        );
        CREATE INDEX IF NOT EXISTS rule_review_history_rule_idx
            ON rule_review_history(rule_id, review_id);
        CREATE TRIGGER IF NOT EXISTS source_no_delete
            BEFORE DELETE ON sources
            BEGIN SELECT RAISE(ABORT, 'source registry is append-only'); END;
        CREATE TRIGGER IF NOT EXISTS documents_no_update
            BEFORE UPDATE ON documents
            BEGIN SELECT RAISE(ABORT, 'document snapshots are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS documents_no_delete
            BEFORE DELETE ON documents
            BEGIN SELECT RAISE(ABORT, 'document snapshots are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS evidence_no_update
            BEFORE UPDATE ON evidence
            BEGIN SELECT RAISE(ABORT, 'evidence records are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS evidence_no_delete
            BEFORE DELETE ON evidence
            BEGIN SELECT RAISE(ABORT, 'evidence records are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS rules_content_immutable
            BEFORE UPDATE ON rules
            WHEN OLD.document_id IS NOT NEW.document_id
              OR OLD.evidence_id IS NOT NEW.evidence_id
              OR OLD.capability IS NOT NEW.capability
              OR OLD.statement IS NOT NEW.statement
              OR OLD.expires_at IS NOT NEW.expires_at
            BEGIN SELECT RAISE(ABORT, 'rule content is immutable'); END;
        CREATE TRIGGER IF NOT EXISTS rules_no_delete
            BEFORE DELETE ON rules
            BEGIN SELECT RAISE(ABORT, 'rule records are append-only'); END;
        CREATE TRIGGER IF NOT EXISTS rules_review_fields_guard
            BEFORE UPDATE OF state, reviewer, reviewed_at ON rules
            WHEN NEW.state NOT IN ('VERIFIED', 'CONFLICT', 'EXPIRED')
              OR NEW.reviewer IS NULL OR length(trim(NEW.reviewer)) = 0
              OR NEW.reviewed_at IS NULL OR length(trim(NEW.reviewed_at)) = 0
            BEGIN SELECT RAISE(ABORT, 'rule review requires a valid decision, reviewer and timestamp'); END;
        CREATE TRIGGER IF NOT EXISTS rules_review_history_append
            AFTER UPDATE OF state, reviewer, reviewed_at ON rules
            WHEN OLD.state IS NOT NEW.state
              OR OLD.reviewer IS NOT NEW.reviewer
              OR OLD.reviewed_at IS NOT NEW.reviewed_at
            BEGIN
                INSERT INTO rule_review_history
                    (rule_id, previous_state, decision, reviewer, reviewed_at)
                VALUES (NEW.rule_id, OLD.state, NEW.state, NEW.reviewer, NEW.reviewed_at);
            END;
        CREATE TRIGGER IF NOT EXISTS rule_review_history_no_update
            BEFORE UPDATE ON rule_review_history
            BEGIN SELECT RAISE(ABORT, 'review history is append-only'); END;
        CREATE TRIGGER IF NOT EXISTS rule_review_history_no_delete
            BEFORE DELETE ON rule_review_history
            BEGIN SELECT RAISE(ABORT, 'review history is append-only'); END;
        """)
        rule_columns = {
            row["name"] for row in self.connection.execute("PRAGMA table_info(rules)")
        }
        if "effect" not in rule_columns:
            self.connection.execute(
                "ALTER TABLE rules ADD COLUMN effect TEXT NOT NULL DEFAULT 'UNSPECIFIED'"
            )
        # Migrate existing databases. Legacy reviewer labels are deliberately
        # left without signed receipts and therefore cannot authorize evaluation.
        review_columns = (
            "reviewer_issuer", "reviewer_subject", "reviewer_key_id",
            "reviewer_assertion_id", "reviewer_company_id", "reviewer_capabilities",
            "reviewer_decisions", "reviewer_authenticated_at", "reviewer_expires_at",
            "reviewer_receipt",
        )
        for table in ("rules", "rule_review_history"):
            present = {
                row["name"] for row in self.connection.execute(f"PRAGMA table_info({table})")
            }
            for column in review_columns:
                if column not in present:
                    self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT")
        self.connection.executescript("""
        DROP TRIGGER IF EXISTS rules_review_fields_guard;
        DROP TRIGGER IF EXISTS rules_review_history_append;
        CREATE TRIGGER rules_review_fields_guard
            BEFORE UPDATE OF state, reviewer, reviewed_at,
                reviewer_issuer, reviewer_subject, reviewer_key_id,
                reviewer_assertion_id, reviewer_company_id, reviewer_capabilities,
                reviewer_decisions, reviewer_authenticated_at, reviewer_expires_at,
                reviewer_receipt ON rules
            WHEN NEW.state NOT IN ('VERIFIED', 'CONFLICT', 'EXPIRED')
              OR NEW.reviewer IS NULL OR length(trim(NEW.reviewer)) = 0
              OR NEW.reviewed_at IS NULL OR length(trim(NEW.reviewed_at)) = 0
              OR NEW.reviewer_issuer IS NULL OR length(trim(NEW.reviewer_issuer)) = 0
              OR NEW.reviewer_subject IS NULL OR length(trim(NEW.reviewer_subject)) = 0
              OR NEW.reviewer_key_id IS NULL OR length(trim(NEW.reviewer_key_id)) = 0
              OR NEW.reviewer_assertion_id IS NULL OR length(trim(NEW.reviewer_assertion_id)) = 0
              OR NEW.reviewer_company_id IS NULL OR length(trim(NEW.reviewer_company_id)) = 0
              OR NEW.reviewer_capabilities IS NULL OR length(trim(NEW.reviewer_capabilities)) = 0
              OR NEW.reviewer_decisions IS NULL OR length(trim(NEW.reviewer_decisions)) = 0
              OR NEW.reviewer_authenticated_at IS NULL OR length(trim(NEW.reviewer_authenticated_at)) = 0
              OR NEW.reviewer_expires_at IS NULL OR length(trim(NEW.reviewer_expires_at)) = 0
              OR NEW.reviewer_receipt IS NULL OR length(trim(NEW.reviewer_receipt)) = 0
            BEGIN SELECT RAISE(ABORT, 'review requires authenticated reviewer authority receipt'); END;
        CREATE TRIGGER rules_review_history_append
            AFTER UPDATE OF state, reviewer, reviewed_at,
                reviewer_issuer, reviewer_subject, reviewer_key_id,
                reviewer_assertion_id, reviewer_company_id, reviewer_capabilities,
                reviewer_decisions, reviewer_authenticated_at, reviewer_expires_at,
                reviewer_receipt ON rules
            WHEN OLD.state IS NOT NEW.state
              OR OLD.reviewer IS NOT NEW.reviewer
              OR OLD.reviewed_at IS NOT NEW.reviewed_at
              OR OLD.reviewer_receipt IS NOT NEW.reviewer_receipt
            BEGIN
                INSERT INTO rule_review_history
                    (rule_id, previous_state, decision, reviewer, reviewed_at,
                     reviewer_issuer, reviewer_subject, reviewer_key_id,
                     reviewer_assertion_id, reviewer_company_id, reviewer_capabilities,
                     reviewer_decisions, reviewer_authenticated_at, reviewer_expires_at,
                     reviewer_receipt)
                VALUES
                    (NEW.rule_id, OLD.state, NEW.state, NEW.reviewer, NEW.reviewed_at,
                     NEW.reviewer_issuer, NEW.reviewer_subject, NEW.reviewer_key_id,
                     NEW.reviewer_assertion_id, NEW.reviewer_company_id, NEW.reviewer_capabilities,
                     NEW.reviewer_decisions, NEW.reviewer_authenticated_at, NEW.reviewer_expires_at,
                     NEW.reviewer_receipt);
            END;
        """)
        self.connection.executescript("""
        CREATE TRIGGER IF NOT EXISTS rules_effect_immutable
            BEFORE UPDATE OF effect ON rules
            WHEN OLD.effect IS NOT NEW.effect
            BEGIN SELECT RAISE(ABORT, 'rule content is immutable'); END;
        CREATE TRIGGER IF NOT EXISTS rules_effect_guard_insert
            BEFORE INSERT ON rules
            WHEN NEW.effect NOT IN ('ALLOW', 'DENY', 'UNSPECIFIED')
            BEGIN SELECT RAISE(ABORT, 'invalid policy effect'); END;
        CREATE TRIGGER IF NOT EXISTS rules_effect_guard_update
            BEFORE UPDATE OF effect ON rules
            WHEN NEW.effect NOT IN ('ALLOW', 'DENY', 'UNSPECIFIED')
            BEGIN SELECT RAISE(ABORT, 'invalid policy effect'); END;
        """)
        self.connection.commit()

    def register_source(self, source: Source) -> Source:
        if not all((source.source_id.strip(), source.company_id.strip(),
                    source.role.strip(), source.title.strip())):
            raise ValueError("source identity, company, role and title are required")
        canonical = canonicalize_url(source.url)
        existing = self.connection.execute(
            "SELECT company_id, role, url FROM sources WHERE source_id=?",
            (source.source_id,),
        ).fetchone()
        if existing:
            if (existing["company_id"], existing["role"], existing["url"]) != (
                source.company_id, source.role, canonical
            ):
                raise ValueError(
                    "source identity is immutable; register a new source_id when company, role or URL changes"
                )
            self.connection.execute(
                "UPDATE sources SET title=? WHERE source_id=?",
                (source.title, source.source_id),
            )
        else:
            self.connection.execute(
                "INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?)",
                (source.source_id, source.company_id, source.role, canonical,
                 source.title, utc_now()),
            )
        self.connection.commit()
        return Source(source.source_id, source.company_id, source.role, canonical, source.title)

    def record_document(self, source_id: str, content: str,
                        fetched_at: str | None = None) -> Document:
        if not isinstance(content, str) or not content.strip():
            raise ValueError("document content must not be empty")
        if not self.connection.execute(
            "SELECT 1 FROM sources WHERE source_id=?", (source_id,)
        ).fetchone():
            raise KeyError(f"unknown source: {source_id}")
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        existing = self.connection.execute(
            "SELECT * FROM documents WHERE source_id=? AND content_sha256=?",
            (source_id, digest),
        ).fetchone()
        if existing:
            return Document(existing["document_id"], source_id, existing["fetched_at"],
                            digest, existing["version"], False)
        latest = self.connection.execute(
            "SELECT COALESCE(MAX(version), 0) AS version FROM documents WHERE source_id=?",
            (source_id,),
        ).fetchone()["version"]
        version = latest + 1
        document_id = hashlib.sha256(f"{source_id}:{digest}".encode()).hexdigest()
        timestamp = fetched_at or utc_now()
        _parse_aware_timestamp(timestamp, "fetched_at")
        self.connection.execute(
            "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?)",
            (document_id, source_id, timestamp, digest, content, version),
        )
        self.connection.commit()
        return Document(document_id, source_id, timestamp, digest, version, version > 1)

    def record_evidence(self, document_id: str, locator: str, excerpt: str) -> str:
        if not locator.strip() or not excerpt.strip():
            raise ValueError("evidence locator and excerpt are required")
        document = self.connection.execute(
            "SELECT content FROM documents WHERE document_id=?", (document_id,)
        ).fetchone()
        if not document:
            raise KeyError(f"unknown document: {document_id}")
        if excerpt not in document["content"]:
            raise ValueError("evidence excerpt must appear in the exact cited document snapshot")
        evidence_id = hashlib.sha256(
            f"{document_id}:{locator}:{excerpt}".encode()
        ).hexdigest()
        self.connection.execute(
            "INSERT OR IGNORE INTO evidence VALUES (?, ?, ?, ?, ?)",
            (evidence_id, document_id, locator, excerpt, utc_now()),
        )
        self.connection.commit()
        return evidence_id

    def propose_rule(self, rule_id: str, document_id: str, evidence_id: str,
                     capability: str, statement: str,
                     expires_at: str | None = None,
                     effect: PolicyEffect | None = None) -> Rule:
        if not all(x.strip() for x in (rule_id, capability, statement)):
            raise ValueError("rule id, capability and statement are required")
        if expires_at is not None:
            _parse_aware_timestamp(expires_at, "expires_at")
        evidence = self.connection.execute(
            "SELECT document_id FROM evidence WHERE evidence_id=?", (evidence_id,)
        ).fetchone()
        if not evidence or evidence["document_id"] != document_id:
            raise ValueError("evidence must belong to the cited document")
        existing = self.connection.execute(
            """SELECT document_id, evidence_id, capability, statement, expires_at, effect
               FROM rules WHERE rule_id=?""",
            (rule_id,),
        ).fetchone()
        policy_effect = PolicyEffect(effect).value if effect is not None else PolicyEffect.UNSPECIFIED.value
        proposed = (document_id, evidence_id, capability, statement, expires_at, policy_effect)
        if existing:
            recorded = tuple(existing[key] for key in (
                "document_id", "evidence_id", "capability", "statement", "expires_at", "effect"
            ))
            if recorded != proposed:
                raise ValueError("rule_id already exists with different rule content")
            return self.get_rule(rule_id)
        self.connection.execute(
            """INSERT INTO rules
               (rule_id, document_id, evidence_id, capability, statement, effect, state, expires_at, reviewer, reviewed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)""",
            (rule_id, document_id, evidence_id, capability, statement, policy_effect,
             RuleState.NEEDS_REVIEW.value, expires_at),
        )
        self.connection.commit()
        return self.get_rule(rule_id)

    def get_rule(self, rule_id: str) -> Rule:
        row = self.connection.execute(
            "SELECT * FROM rules WHERE rule_id=?", (rule_id,)
        ).fetchone()
        if not row:
            raise KeyError(rule_id)
        return Rule(row["rule_id"], row["document_id"], row["capability"],
                    row["statement"], PolicyEffect(row["effect"]), RuleState(row["state"]), row["expires_at"])

    def review_rule(self, rule_id: str, reviewer_assertion: str,
                    decision: RuleState) -> Rule:
        """Record a review only when a trusted verifier proves scoped authority.

        The second argument is a signed assertion, never a free-form reviewer name.
        """
        if decision not in (RuleState.VERIFIED, RuleState.CONFLICT, RuleState.EXPIRED):
            raise ValueError("review decision must be VERIFIED, CONFLICT or EXPIRED")
        current = self.connection.execute(
            """SELECT r.capability, s.company_id FROM rules r
               JOIN documents d ON d.document_id=r.document_id
               JOIN sources s ON s.source_id=d.source_id WHERE r.rule_id=?""",
            (rule_id,),
        ).fetchone()
        if current is None:
            raise KeyError(rule_id)
        verified = authorize_review(
            self.reviewer_verifier, reviewer_assertion,
            company_id=current["company_id"], capability=current["capability"],
            decision=decision.value,
        )
        timestamp = utc_now()
        values = (
            decision.value, verified.subject, timestamp,
            verified.issuer, verified.subject, verified.key_id, verified.assertion_id,
            verified.company_id,
            json.dumps(sorted(verified.capabilities), separators=(",", ":")),
            json.dumps(sorted(verified.decisions), separators=(",", ":")),
            verified.authenticated_at, verified.expires_at, verified.receipt, rule_id,
        )
        try:
            self.connection.execute(
                """UPDATE rules SET state=?, reviewer=?, reviewed_at=?,
                   reviewer_issuer=?, reviewer_subject=?, reviewer_key_id=?,
                   reviewer_assertion_id=?, reviewer_company_id=?, reviewer_capabilities=?,
                   reviewer_decisions=?, reviewer_authenticated_at=?, reviewer_expires_at=?,
                   reviewer_receipt=? WHERE rule_id=?""",
                values,
            )
            # The matching review history row is appended atomically by SQLite.
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        return self.get_rule(rule_id)

    def get_review_history(self, rule_id: str) -> tuple[dict, ...]:
        if not self.connection.execute(
            "SELECT 1 FROM rules WHERE rule_id=?", (rule_id,)
        ).fetchone():
            raise KeyError(rule_id)
        rows = self.connection.execute(
            """SELECT review_id, rule_id, previous_state, decision, reviewer, reviewed_at
               FROM rule_review_history WHERE rule_id=? ORDER BY review_id""",
            (rule_id,),
        ).fetchall()
        return tuple(dict(row) for row in rows)

    def evaluate(self, capability: str, now: str | None = None, max_age_seconds: int | None = None) -> Evaluation:
        rows = self.connection.execute(
            """SELECT r.rule_id, r.state, r.effect, r.expires_at, r.document_id,
                      r.reviewer_issuer, r.reviewer_subject, r.reviewer_key_id,
                      r.reviewer_assertion_id, r.reviewer_company_id, r.reviewer_receipt,
                      d.source_id, s.company_id
               FROM rules r
               JOIN documents d ON d.document_id=r.document_id
               JOIN sources s ON s.source_id=d.source_id
               WHERE r.capability=?
               ORDER BY r.rule_id""",
            (capability,),
        ).fetchall()
        ids = tuple(row["rule_id"] for row in rows)
        if not rows:
            return Evaluation(capability, CapabilityState.BLOCKED_NO_POLICY, (),
                              "no reviewed policy evidence exists")
        current = now or utc_now()
        current_dt = _parse_aware_timestamp(current, "now")
        # A persisted review is trusted only while its signed authorization receipt
        # can be re-verified by the configured identity provider. Names/labels and
        # legacy rows never authorize a positive decision.
        for row in rows:
            if not verify_review_receipt(
                self.reviewer_verifier, row["reviewer_receipt"],
                issuer=row["reviewer_issuer"], subject=row["reviewer_subject"],
                key_id=row["reviewer_key_id"], assertion_id=row["reviewer_assertion_id"],
                company_id=row["company_id"], capability=capability,
                decision=row["state"], now=current_dt,
            ):
                return Evaluation(
                    capability, CapabilityState.BLOCKED_REVIEW, ids,
                    "reviewer identity or scoped authorization receipt is missing, invalid, revoked, or expired",
                )
        # A rule is tied to the exact document snapshot it was reviewed against.
        # Any newer snapshot from that source invalidates the old review until
        # the changed policy has been examined and new evidence is approved.
        for row in rows:
            latest = self.connection.execute(
                """SELECT document_id FROM documents
                   WHERE source_id=? ORDER BY version DESC LIMIT 1""",
                (row["source_id"],),
            ).fetchone()
            if not latest or latest["document_id"] != row["document_id"]:
                return Evaluation(
                    capability, CapabilityState.BLOCKED_REVIEW, ids,
                    "a newer source snapshot exists; policy rules require re-review",
                )
        if any(row["state"] == RuleState.CONFLICT.value for row in rows):
            return Evaluation(capability, CapabilityState.BLOCKED_CONFLICT, ids,
                              "conflicting policy evidence requires review")
        if any(
            row["state"] == RuleState.EXPIRED.value
            or (row["expires_at"] and
                _parse_aware_timestamp(row["expires_at"], "expires_at") <= current_dt)
            for row in rows
        ):
            return Evaluation(capability, CapabilityState.BLOCKED_EXPIRED, ids,
                              "policy evidence is expired")
        if max_age_seconds is not None:
            if max_age_seconds < 0:
                raise ValueError("max_age_seconds must be non-negative")
            docs = self.connection.execute(
                "SELECT DISTINCT d.fetched_at FROM documents d JOIN rules r ON r.document_id=d.document_id WHERE r.capability=?",
                (capability,),
            ).fetchall()
            for doc in docs:
                fetched_dt = _parse_aware_timestamp(doc["fetched_at"], "fetched_at")
                if current_dt - fetched_dt > timedelta(seconds=max_age_seconds):
                    return Evaluation(capability, CapabilityState.BLOCKED_EXPIRED, ids, "source snapshot is stale")
        if any(row["state"] != RuleState.VERIFIED.value for row in rows):
            return Evaluation(capability, CapabilityState.BLOCKED_REVIEW, ids,
                              "one or more rules have not been manually verified")
        if any(row["effect"] not in (PolicyEffect.ALLOW.value, PolicyEffect.DENY.value) for row in rows):
            return Evaluation(capability, CapabilityState.BLOCKED_REVIEW, ids,
                              "one or more verified rules lack an explicit ALLOW or DENY effect")
        if any(row["effect"] == PolicyEffect.DENY.value for row in rows):
            return Evaluation(capability, CapabilityState.BLOCKED_POLICY_DENY, ids,
                              "at least one verified policy rule explicitly denies this capability")
        return Evaluation(capability, CapabilityState.ALLOWED, ids,
                          "all current verified rules explicitly allow this capability")

    def export_snapshot(self) -> str:
        """Deterministic JSON snapshot for audit; excludes document body/secrets."""
        result = {}
        tables = ["sources", "documents", "evidence", "rules", "rule_review_history"]
        monitor_exists = self.connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='monitor_checks'"
        ).fetchone()
        if monitor_exists:
            tables.append("monitor_checks")
        for table in tables:
            columns = (
                "document_id, source_id, fetched_at, content_sha256, version"
                if table == "documents" else "*"
            )
            rows = self.connection.execute(
                f"SELECT {columns} FROM {table} ORDER BY 1"
            ).fetchall()
            result[table] = [dict(row) for row in rows]
        return json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
