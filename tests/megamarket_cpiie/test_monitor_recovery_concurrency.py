import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from products.megamarket.cpiie import CPIIERegistry, Source
from products.megamarket.cpiie.fetch import OfficialSourceFetcher
from products.megamarket.cpiie.monitor import PolicyMonitor


class RecoveryConcurrencyTests(unittest.TestCase):
    def _make_pending(self, db_path, check_id):
        registry = CPIIERegistry(str(db_path))
        registry.register_source(Source(
            "policy", "company-a", "terms",
            "https://policy.example.org/terms", "Terms",
        ))
        monitor = PolicyMonitor(registry, OfficialSourceFetcher(registry))
        monitor._append_event(
            check_id, "policy", "2026-11-17T00:00:00+00:00", "STARTED"
        )
        registry.close()

    def test_two_recovery_workers_append_only_one_terminal_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "cpiie.sqlite3"
            self._make_pending(db_path, "shared-check")
            barrier = threading.Barrier(2)

            def recover():
                registry = CPIIERegistry(str(db_path))
                try:
                    monitor = PolicyMonitor(
                        registry, OfficialSourceFetcher(registry)
                    )
                    barrier.wait(timeout=5)
                    return monitor.recover_pending("policy")
                finally:
                    registry.close()

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: recover(), range(2)))

            self.assertEqual(sorted(results), [0, 1])
            registry = CPIIERegistry(str(db_path))
            try:
                rows = registry.connection.execute(
                    "SELECT status FROM monitor_checks "
                    "WHERE check_id='shared-check' ORDER BY event_id"
                ).fetchall()
                self.assertEqual([row["status"] for row in rows],
                                 ["STARTED", "FAILED"])
            finally:
                registry.close()

    def test_recovery_rolls_back_all_receipts_if_one_insert_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "cpiie.sqlite3"
            self._make_pending(db_path, "check-one")
            registry = CPIIERegistry(str(db_path))
            try:
                monitor = PolicyMonitor(registry, OfficialSourceFetcher(registry))
                monitor._append_event(
                    "check-two", "policy", "2026-11-17T00:00:01+00:00", "STARTED"
                )
                registry.connection.execute("""
                    CREATE TRIGGER reject_recovery BEFORE INSERT ON monitor_checks
                    WHEN NEW.status='FAILED'
                    BEGIN SELECT RAISE(ABORT, 'simulated recovery storage failure'); END
                """)
                registry.connection.commit()

                with self.assertRaisesRegex(Exception, "simulated recovery storage failure"):
                    monitor.recover_pending("policy")

                pending = registry.connection.execute(
                    "SELECT COUNT(*) FROM monitor_checks WHERE status='STARTED'"
                ).fetchone()[0]
                terminal = registry.connection.execute(
                    "SELECT COUNT(*) FROM monitor_checks WHERE status='FAILED'"
                ).fetchone()[0]
                self.assertEqual(pending, 2)
                self.assertEqual(terminal, 0)

                registry.connection.execute("DROP TRIGGER reject_recovery")
                registry.connection.commit()
                self.assertEqual(monitor.recover_pending("policy"), 2)
                self.assertEqual(monitor.recover_pending("policy"), 0)
            finally:
                registry.close()


if __name__ == "__main__":
    unittest.main()
