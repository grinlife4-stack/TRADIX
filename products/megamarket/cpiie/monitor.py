"""Explicit, read-only polling for registered CPIIE sources."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

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
    """Poll registered sources on demand with durable start/terminal audit events.

    A committed STARTED event precedes fetching. SUCCESS or FAILED is appended
    afterward. If a process or database fails between those steps, STARTED
    remains as an explicit unresolved check rather than leaving an untraceable
    document. Scheduling remains external.
    """

    def __init__(self, registry: CPIIERegistry, fetcher: OfficialSourceFetcher):
        if fetcher.registry is not registry:
            raise ValueError("fetcher and monitor must share one registry")
        self.registry = registry
        self.fetcher = fetcher
        self._migrate_monitor_checks()

    def _migrate_monitor_checks(self) -> None:
        db = self.registry.connection
        db.execute("""
            CREATE TABLE IF NOT EXISTS cpiie_schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
        """)
        columns = {
            row["name"] for row in db.execute("PRAGMA table_info(monitor_checks)")
        }
        if columns and "phase" not in columns:
            # Rebuild old installations: CREATE TABLE IF NOT EXISTS cannot add
            # constraints or columns to an existing SQLite table.
            db.execute("DROP TRIGGER IF EXISTS monitor_checks_no_update")
            db.execute("DROP TRIGGER IF EXISTS monitor_checks_no_delete")
            db.execute("ALTER TABLE monitor_checks RENAME TO monitor_checks_legacy")
            self._create_monitor_table()
            legacy = db.execute(
                "SELECT check_id, source_id, checked_at, status, version, changed, "
                "content_sha256, error FROM monitor_checks_legacy ORDER BY check_id"
            ).fetchall()
            for row in legacy:
                db.execute(
                    """INSERT INTO monitor_checks
                       (check_id, source_id, checked_at, status, version, changed,
                        content_sha256, error)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (f"legacy-{row['check_id']}", row["source_id"], row["checked_at"],
                     row["status"], row["version"], row["changed"],
                     row["content_sha256"], row["error"]),
                )
            db.execute("DROP TABLE monitor_checks_legacy")
        else:
            self._create_monitor_table()
        db.execute(
            "INSERT OR IGNORE INTO cpiie_schema_migrations(version, applied_at) VALUES (1, ?)",
            (utc_now(),),
        )
        db.execute("""
            CREATE TRIGGER IF NOT EXISTS monitor_checks_no_update
            BEFORE UPDATE ON monitor_checks
            BEGIN SELECT RAISE(ABORT, 'monitor history is append-only'); END
        """)
        db.execute("""
            CREATE TRIGGER IF NOT EXISTS monitor_checks_no_delete
            BEFORE DELETE ON monitor_checks
            BEGIN SELECT RAISE(ABORT, 'monitor history is append-only'); END
        """)
        db.commit()

    def _create_monitor_table(self) -> None:
        self.registry.connection.execute("""
            CREATE TABLE IF NOT EXISTS monitor_checks (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                check_id TEXT NOT NULL,
                source_id TEXT NOT NULL REFERENCES sources(source_id),
                checked_at TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('STARTED', 'SUCCESS', 'FAILED')),
                version INTEGER,
                changed INTEGER NOT NULL CHECK(changed IN (0, 1)),
                content_sha256 TEXT,
                error TEXT,
                CHECK (
                    (status = 'STARTED' AND version IS NULL AND changed = 0
                     AND content_sha256 IS NULL AND error IS NULL)
                    OR
                    (status = 'SUCCESS' AND version IS NOT NULL
                     AND content_sha256 IS NOT NULL AND error IS NULL)
                    OR
                    (status = 'FAILED' AND version IS NULL AND changed = 0
                     AND content_sha256 IS NULL AND error IS NOT NULL)
                )
            )
        """)
        self.registry.connection.execute(
            "CREATE INDEX IF NOT EXISTS monitor_checks_group_idx "
            "ON monitor_checks(source_id, check_id, event_id)"
        )

    def _append_event(self, check_id: str, source_id: str, checked_at: str,
                      status: str, version: int | None = None,
                      changed: bool = False, content_sha256: str | None = None,
                      error: str | None = None) -> None:
        db = self.registry.connection
        db.execute(
            """INSERT INTO monitor_checks
               (check_id, source_id, checked_at, status, version, changed,
                content_sha256, error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (check_id, source_id, checked_at, status, version, int(changed),
             content_sha256, error),
        )
        db.commit()

    def check_source(self, source_id: str, *, allowed_hosts: set[str]) -> MonitorResult:
        if not self.registry.connection.execute(
            "SELECT 1 FROM sources WHERE source_id=?", (source_id,)
        ).fetchone():
            raise KeyError(f"unknown source: {source_id}")

        checked_at = utc_now()
        check_id = uuid4().hex
        # This commit is intentionally before network I/O and document storage.
        self._append_event(check_id, source_id, checked_at, "STARTED")
        try:
            receipt = self.fetcher.fetch(source_id, allowed_hosts=allowed_hosts)
            result = MonitorResult(
                source_id, checked_at, "SUCCESS", receipt.document.version,
                receipt.document.changed, receipt.document.content_sha256, None,
            )
        except (FetchError, OSError, ValueError) as exc:
            result = MonitorResult(source_id, checked_at, "FAILED", None, False, None,
                                   f"{type(exc).__name__}: {exc}")
        except Exception as exc:
            # Preserve a durable failure receipt, but do not disguise an
            # unexpected programming/runtime failure as an ordinary fetch miss.
            self._append_event(
                check_id, source_id, checked_at, "FAILED",
                error=f"UNEXPECTED {type(exc).__name__}: {exc}",
            )
            raise

        self._append_event(
            check_id, source_id, checked_at, result.status, result.version,
            result.changed, result.content_sha256, result.error,
        )
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
            """SELECT e.source_id, e.checked_at, e.status, e.version, e.changed,
                      e.content_sha256, e.error
               FROM monitor_checks e
               JOIN (
                   SELECT check_id, MAX(event_id) AS latest_event
                   FROM monitor_checks WHERE source_id=?
                   GROUP BY check_id
               ) latest ON latest.latest_event=e.event_id
               ORDER BY e.event_id DESC LIMIT ?""",
            (source_id, limit),
        ).fetchall()
        return tuple(MonitorResult(
            row["source_id"], row["checked_at"],
            "PENDING" if row["status"] == "STARTED" else row["status"],
            row["version"], bool(row["changed"]), row["content_sha256"], row["error"],
        ) for row in rows)
