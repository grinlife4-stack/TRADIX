import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from products.megamarket.cpiie import CPIIERegistry, Source
from products.megamarket.cpiie.fetch import OfficialSourceFetcher
from products.megamarket.cpiie.monitor import PolicyMonitor


class ProcessKillRecoveryTests(unittest.TestCase):
    def test_real_process_kill_leaves_recoverable_started_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "cpiie.sqlite3"
            marker = Path(tmp) / "fetch-entered"

            registry = CPIIERegistry(str(db_path))
            registry.register_source(Source(
                "policy", "company-a", "terms",
                "https://policy.example.org/terms", "Terms",
            ))
            registry.close()

            child_code = r"""
import pathlib
import sys
import time
from products.megamarket.cpiie import CPIIERegistry
from products.megamarket.cpiie.fetch import OfficialSourceFetcher
from products.megamarket.cpiie.monitor import PolicyMonitor

db_path = sys.argv[1]
marker_path = pathlib.Path(sys.argv[2])
registry = CPIIERegistry(db_path)
fetcher = OfficialSourceFetcher(registry)
monitor = PolicyMonitor(registry, fetcher)

def block_after_started_event(*args, **kwargs):
    marker_path.write_text("fetch reached after STARTED commit", encoding="utf-8")
    while True:
        time.sleep(1)

fetcher.fetch = block_after_started_event
monitor.check_source("policy", allowed_hosts={"policy.example.org"})
"""
            child = subprocess.Popen(
                [sys.executable, "-c", child_code, str(db_path), str(marker)],
                cwd=os.getcwd(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline and not marker.exists():
                if child.poll() is not None:
                    stderr = child.stderr.read().decode("utf-8", errors="replace")
                    self.fail(f"child exited before interruption point: {stderr}")
                time.sleep(0.05)

            if not marker.exists():
                child.kill()
                child.wait(timeout=5)
                self.fail("child never reached the post-STARTED fetch point")

            # Terminate the actual worker process while its check is in flight.
            child.kill()
            child.wait(timeout=5)
            self.assertIsNotNone(child.returncode)

            recovered_registry = CPIIERegistry(str(db_path))
            recovered_monitor = PolicyMonitor(
                recovered_registry,
                OfficialSourceFetcher(recovered_registry),
            )
            pending = recovered_monitor.history("policy")
            self.assertEqual(len(pending), 1)
            self.assertEqual(pending[0].status, "PENDING")

            self.assertEqual(recovered_monitor.recover_pending("policy"), 1)
            recovered = recovered_monitor.history("policy")
            self.assertEqual(recovered[0].status, "FAILED")
            self.assertIn("INTERRUPTED", recovered[0].error)
            self.assertEqual(recovered_monitor.recover_pending("policy"), 0)
            recovered_registry.close()


if __name__ == "__main__":
    unittest.main()
