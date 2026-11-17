"""Explicit, read-only polling for registered CPIIE sources."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from . import CPIIERegistry, utc_now
from .fetch import FetchError, OfficialSourceFetcher


@dataclass(frozen=True)
class MonitorResult:
    source_id: str
    checked_at: str
    status: str
    version: int | None
    changed: bool
    content_sha256: str | None
    error: str | None


class PolicyMonitor:
    """Poll registered sources on demand and persist a compact check history.

    Scheduling is deliberately external. This class never creates timers or
    runs in the background; the caller decides when a check is authorized.
    """

    def __init__(self, registry: CPIIERegistry, fetcher: OfficialSourceFetcher):
        if fetcher.registry is not registry:
            raise ValueError("fetcher and monitor must share one registry")
        self.registry = registry
        self.fetcher = fetcher
        self.registry.connection.execute("""
            CREATE TABLE IF NOT EXISTS monitor_checks (
                check_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL REFERENCES sources(source_id),
                checked_at TEXT NOT NULL,
                status TEXT NOT NULL,
                version INTEGER,
                changed INTEGER NOT NULL,
                content_sha256 TEXT,
                error TEXT
            )
        """)
        self.registry.connection.commit()

    def check_source(self, source_id: str, *, allowed_hosts: set[str]) -> MonitorResult:
        checked_at = utc_now()
        try:
            receipt = self.fetcher.fetch(source_id, allowed_hosts=allowed_hosts)
            result = MonitorResult(
                source_id, checked_at, "SUCCESS", receipt.document.version,
                receipt.document.changed, receipt.document.content_sha256, None,
            )
        except (FetchError, KeyError, ValueError) as exc:
            result = MonitorResult(source_id, checked_at, "FAILED", None, False, None,
                                   f"{type(exc).__name__}: {exc}")
        self.registry.connection.execute(
            """INSERT INTO monitor_checks
               (source_id, checked_at, status, version, changed, content_sha256, error)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (result.source_id, result.checked_at, result.status, result.version,
             int(result.changed), result.content_sha256, result.error),
        )
        self.registry.connection.commit()
        return result

    def check_all(self, *, allowed_hosts: set[str]) -> tuple[MonitorResult, ...]:
        rows = self.registry.connection.execute(
            "SELECT source_id FROM sources ORDER BY source_id"
        ).fetchall()
        return tuple(self.check_source(row["source_id"], allowed_hosts=allowed_hosts)
                     for row in rows)

    def history(self, source_id: str, *, limit: int = 20) -> tuple[MonitorResult, ...]:
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        rows = self.registry.connection.execute(
            """SELECT source_id, checked_at, status, version, changed,
                      content_sha256, error
               FROM monitor_checks WHERE source_id=?
               ORDER BY check_id DESC LIMIT ?""",
            (source_id, limit),
        ).fetchall()
        return tuple(MonitorResult(
            row["source_id"], row["checked_at"], row["status"], row["version"],
            bool(row["changed"]), row["content_sha256"], row["error"],
        ) for row in rows)
