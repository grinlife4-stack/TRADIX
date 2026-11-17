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


class RuleState(StrEnum):
    NEEDS_REVIEW = "NEEDS_REVIEW"
    VERIFIED = "VERIFIED"
    CONFLICT = "CONFLICT"
    EXPIRED = "EXPIRED"


class CapabilityState(StrEnum):
    BLOCKED_NO_POLICY = "BLOCKED_NO_POLICY"
    BLOCKED_REVIEW = "BLOCKED_REVIEW"
    BLOCKED_CONFLICT = "BLOCKED_CONFLICT"
    BLOCKED_EXPIRED = "BLOCKED_EXPIRED"
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

    def __init__(self, database: str | Path = ":memory:") -> None:
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
            state TEXT NOT NULL,
            expires_at TEXT,
            reviewer TEXT,
            reviewed_at TEXT
        );
        CREATE INDEX IF NOT EXISTS rules_capability_idx ON rules(capability);
        """)
        self.connection.commit()

    def register_source(self, source: Source) -> Source:
        if not all((source.source_id.strip(), source.company_id.strip(),
                    source.role.strip(), source.title.strip())):
            raise ValueError("source identity, company, role and title are required")
        canonical = canonicalize_url(source.url)
        self.connection.execute(
            """INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(source_id) DO UPDATE SET
               company_id=excluded.company_id, role=excluded.role,
               url=excluded.url, title=excluded.title""",
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
        self.connection.execute(
            "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?)",
            (document_id, source_id, timestamp, digest, content, version),
        )
        self.connection.commit()
        return Document(document_id, source_id, timestamp, digest, version, version > 1)

    def record_evidence(self, document_id: str, locator: str, excerpt: str) -> str:
        if not locator.strip() or not excerpt.strip():
            raise ValueError("evidence locator and excerpt are required")
        if not self.connection.execute(
            "SELECT 1 FROM documents WHERE document_id=?", (document_id,)
        ).fetchone():
            raise KeyError(f"unknown document: {document_id}")
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
                     expires_at: str | None = None) -> Rule:
        if not all(x.strip() for x in (rule_id, capability, statement)):
            raise ValueError("rule id, capability and statement are required")
        evidence = self.connection.execute(
            "SELECT document_id FROM evidence WHERE evidence_id=?", (evidence_id,)
        ).fetchone()
        if not evidence or evidence["document_id"] != document_id:
            raise ValueError("evidence must belong to the cited document")
        existing = self.connection.execute(
            """SELECT document_id, evidence_id, capability, statement, expires_at
               FROM rules WHERE rule_id=?""",
            (rule_id,),
        ).fetchone()
        proposed = (document_id, evidence_id, capability, statement, expires_at)
        if existing:
            recorded = tuple(existing[key] for key in (
                "document_id", "evidence_id", "capability", "statement", "expires_at"
            ))
            if recorded != proposed:
                raise ValueError("rule_id already exists with different rule content")
            return self.get_rule(rule_id)
        self.connection.execute(
            """INSERT INTO rules VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL)""",
            (rule_id, document_id, evidence_id, capability, statement,
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
                    row["statement"], RuleState(row["state"]), row["expires_at"])

    def review_rule(self, rule_id: str, reviewer: str,
                    decision: RuleState) -> Rule:
        if not reviewer.strip():
            raise ValueError("a named reviewer is required")
        if decision not in (RuleState.VERIFIED, RuleState.CONFLICT, RuleState.EXPIRED):
            raise ValueError("review decision must be VERIFIED, CONFLICT or EXPIRED")
        cursor = self.connection.execute(
            "UPDATE rules SET state=?, reviewer=?, reviewed_at=? WHERE rule_id=?",
            (decision.value, reviewer, utc_now(), rule_id),
        )
        if cursor.rowcount == 0:
            raise KeyError(rule_id)
        self.connection.commit()
        return self.get_rule(rule_id)

    def evaluate(self, capability: str, now: str | None = None, max_age_seconds: int | None = None) -> Evaluation:
        rows = self.connection.execute(
            "SELECT rule_id, state, expires_at FROM rules WHERE capability=? ORDER BY rule_id",
            (capability,),
        ).fetchall()
        ids = tuple(row["rule_id"] for row in rows)
        if not rows:
            return Evaluation(capability, CapabilityState.BLOCKED_NO_POLICY, (),
                              "no reviewed policy evidence exists")
        current = now or utc_now()
        if any(row["state"] == RuleState.CONFLICT.value for row in rows):
            return Evaluation(capability, CapabilityState.BLOCKED_CONFLICT, ids,
                              "conflicting policy evidence requires review")
        if any(row["state"] == RuleState.EXPIRED.value or
               (row["expires_at"] and row["expires_at"] <= current) for row in rows):
            return Evaluation(capability, CapabilityState.BLOCKED_EXPIRED, ids,
                              "policy evidence is expired")
        if max_age_seconds is not None:
            if max_age_seconds < 0:
                raise ValueError("max_age_seconds must be non-negative")
            docs = self.connection.execute(
                "SELECT DISTINCT d.fetched_at FROM documents d JOIN rules r ON r.document_id=d.document_id WHERE r.capability=?",
                (capability,),
            ).fetchall()
            now_dt = datetime.fromisoformat(current)
            for doc in docs:
                if now_dt - datetime.fromisoformat(doc["fetched_at"]) > timedelta(seconds=max_age_seconds):
                    return Evaluation(capability, CapabilityState.BLOCKED_EXPIRED, ids, "source snapshot is stale")
        if any(row["state"] != RuleState.VERIFIED.value for row in rows):
            return Evaluation(capability, CapabilityState.BLOCKED_REVIEW, ids,
                              "one or more rules have not been manually verified")
        return Evaluation(capability, CapabilityState.ALLOWED, ids,
                          "all registered rules are manually verified and current")

    def export_snapshot(self) -> str:
        """Deterministic JSON snapshot for audit; excludes document body/secrets."""
        result = {}
        for table in ("sources", "documents", "evidence", "rules"):
            columns = "document_id, source_id, fetched_at, content_sha256, version" if table == "documents" else "*"
            rows = self.connection.execute(f"SELECT {columns} FROM {table} ORDER BY 1").fetchall()
            result[table] = [dict(row) for row in rows]
        return json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
