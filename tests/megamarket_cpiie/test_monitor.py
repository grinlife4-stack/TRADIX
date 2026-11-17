import unittest
from email.message import Message
from unittest.mock import Mock

from products.megamarket.cpiie import CPIIERegistry, Source
from products.megamarket.cpiie.fetch import OfficialSourceFetcher
from products.megamarket.cpiie.monitor import PolicyMonitor

class FakeResponse:
    def __init__(self, body=b"terms", final_url="https://policy.example.org/terms"):
        self.body = body
        self.status = 200
        self.final_url = final_url
        self.headers = Message()
        self.headers["Content-Type"] = "text/plain; charset=utf-8"
        self.headers["Content-Length"] = str(len(body))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def geturl(self):
        return self.final_url

    def read(self, limit=-1):
        return self.body[:limit]



class PolicyMonitorTests(unittest.TestCase):
    def setUp(self):
        self.registry = CPIIERegistry()
        self.registry.register_source(Source(
            "policy", "company-a", "terms",
            "https://policy.example.org/terms", "Terms",
        ))
        self.opener = Mock()
        self.fetcher = OfficialSourceFetcher(self.registry, opener=self.opener)
        self.monitor = PolicyMonitor(self.registry, self.fetcher)

    def tearDown(self):
        self.registry.close()

    def test_records_new_version_and_unchanged_check(self):
        self.opener.open.side_effect = [
            FakeResponse(body=b"terms version one"),
            FakeResponse(body=b"terms version two"),
        ]
        first = self.monitor.check_source(
            "policy", allowed_hosts={"policy.example.org"}
        )
        second = self.monitor.check_source(
            "policy", allowed_hosts={"policy.example.org"}
        )
        self.assertEqual(first.status, "SUCCESS")
        self.assertEqual(first.version, 1)
        self.assertFalse(first.changed)
        self.assertEqual(second.version, 2)
        self.assertTrue(second.changed)
        history = self.monitor.history("policy")
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].version, 2)

    def test_failed_fetch_is_recorded(self):
        self.opener.open.side_effect = OSError("network unavailable")
        result = self.monitor.check_source(
            "policy", allowed_hosts={"policy.example.org"}
        )
        self.assertEqual(result.status, "FAILED")
        self.assertIn("network unavailable", result.error)
        self.assertEqual(self.monitor.history("policy")[0].status, "FAILED")

    def test_unknown_source_does_not_write_history(self):
        with self.assertRaises(KeyError):
            self.monitor.check_source("missing", allowed_hosts={"policy.example.org"})
        self.assertEqual(
            self.registry.connection.execute(
                "SELECT COUNT(*) FROM monitor_checks"
            ).fetchone()[0],
            0,
        )

    def test_monitor_history_is_append_only(self):
        self.opener.side_effect = OSError("offline")
        self.monitor.check_source("policy", allowed_hosts={"policy.example.org"})
        with self.assertRaisesRegex(Exception, "append-only"):
            self.registry.connection.execute(
                "UPDATE monitor_checks SET error='tampered' WHERE source_id='policy'"
            )
        self.registry.connection.rollback()
        with self.assertRaisesRegex(Exception, "append-only"):
            self.registry.connection.execute(
                "DELETE FROM monitor_checks WHERE source_id='policy'"
            )
        self.registry.connection.rollback()
        self.assertIn("offline", self.monitor.history("policy")[0].error)

    def test_monitor_history_rejects_invalid_status_shape(self):
        with self.assertRaises(Exception):
            self.registry.connection.execute(
                """INSERT INTO monitor_checks
                   (source_id, checked_at, status, version, changed, content_sha256, error)
                   VALUES ('policy', '2026-11-17T00:00:00+00:00', 'SUCCESS',
                           NULL, 0, NULL, 'invalid success')"""
            )
        self.registry.connection.rollback()
        self.assertEqual(self.monitor.history("policy"), ())

    def test_check_all_uses_registered_sources(self):
        self.opener.open.return_value = FakeResponse()
        results = self.monitor.check_all(allowed_hosts={"policy.example.org"})
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source_id, "policy")


if __name__ == "__main__":
    unittest.main()
