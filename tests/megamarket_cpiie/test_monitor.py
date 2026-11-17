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

    def test_check_all_uses_registered_sources(self):
        self.opener.open.return_value = FakeResponse()
        results = self.monitor.check_all(allowed_hosts={"policy.example.org"})
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source_id, "policy")


if __name__ == "__main__":
    unittest.main()
