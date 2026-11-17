import hashlib
import hmac
import json
import sqlite3
import unittest

from products.megamarket.cpiie.audit_ledger import (
    AuditIntegrityError, AuditLedger, GENESIS_HASH, verify_events,
    verify_signed_export,
)


class TestSigner:
    """Test-only signer. Production must inject an asymmetric KMS/HSM-backed signer."""
    def __init__(self, key=b"test-only-key"):
        self.key = key

    def sign(self, message):
        return hmac.new(self.key, message, hashlib.sha256).digest()

    def verify(self, message, signature):
        return hmac.compare_digest(self.sign(message), signature)


class AuditLedgerTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.ledger = AuditLedger(self.db)
        self.signer = TestSigner()

    def tearDown(self):
        self.db.close()

    def test_append_and_verify_chain(self):
        first = self.ledger.append("source.registered", {"source_id": "s-1"})
        second = self.ledger.append("document.recorded", {"document_id": "d-1"})
        self.assertEqual(first["sequence"], 1)
        self.assertEqual(second["sequence"], 2)
        self.assertEqual(second["previous_hash"], first["event_hash"])
        self.assertEqual(self.ledger.verify(), second["event_hash"])

    def test_canonical_json_is_stable_for_mapping_order(self):
        a = self.ledger.append("fixture", {"b": 2, "a": 1})
        self.assertEqual(a["event_hash"], verify_events(self.ledger.events()))

    def test_rejects_naive_timestamp(self):
        with self.assertRaisesRegex(ValueError, "timezone offset"):
            self.ledger.append("fixture", {}, "2026-11-17T12:00:00")

    def test_rejects_non_json_payload(self):
        with self.assertRaises(ValueError):
            self.ledger.append("fixture", {"not_json": object()})

    def test_detects_payload_tampering(self):
        self.ledger.append("fixture", {"value": "original"})
        events = self.ledger.events()
        events[0]["payload"]["value"] = "tampered"
        with self.assertRaisesRegex(AuditIntegrityError, "hash mismatch"):
            verify_events(events)

    def test_detects_deletion_and_sequence_gap(self):
        self.ledger.append("one", {})
        self.ledger.append("two", {})
        with self.assertRaisesRegex(AuditIntegrityError, "sequence gap"):
            verify_events(self.ledger.events()[1:])

    def test_detects_reordering(self):
        self.ledger.append("one", {})
        self.ledger.append("two", {})
        events = list(reversed(self.ledger.events()))
        with self.assertRaises(AuditIntegrityError):
            verify_events(events)

    def test_detects_duplicate_sequence(self):
        self.ledger.append("one", {})
        self.ledger.append("two", {})
        events = self.ledger.events()
        events[1]["sequence"] = 1
        with self.assertRaisesRegex(AuditIntegrityError, "sequence gap"):
            verify_events(events)

    def test_database_rows_are_append_only_under_normal_sql(self):
        event = self.ledger.append("fixture", {})
        with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
            self.db.execute("UPDATE cpiie_audit_events SET event_type='changed' WHERE sequence=1")
        self.db.rollback()
        with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
            self.db.execute("DELETE FROM cpiie_audit_events WHERE sequence=1")
        self.db.rollback()
        self.assertEqual(self.ledger.verify(), event["event_hash"])

    def test_signed_export_round_trip(self):
        self.ledger.append("source.registered", {"source_id": "s-1"})
        export = self.ledger.signed_export(self.signer)
        self.assertEqual(
            verify_signed_export(export, self.signer, GENESIS_HASH),
            export["document"]["head_hash"],
        )

    def test_rejects_missing_signing_key(self):
        self.ledger.append("fixture", {})
        with self.assertRaisesRegex(AuditIntegrityError, "signing key"):
            self.ledger.signed_export(None)
        export = self.ledger.signed_export(self.signer)
        with self.assertRaisesRegex(AuditIntegrityError, "verification key"):
            verify_signed_export(export, None)

    def test_rejects_invalid_signature(self):
        self.ledger.append("fixture", {})
        export = self.ledger.signed_export(self.signer)
        export["signature_base64"] = self.ledger.signed_export(TestSigner(b"wrong"))["signature_base64"]
        with self.assertRaisesRegex(AuditIntegrityError, "signature is invalid"):
            verify_signed_export(export, self.signer)

    def test_rejects_export_replay_against_unknown_anchor(self):
        self.ledger.append("one", {})
        export = self.ledger.signed_export(self.signer)
        with self.assertRaisesRegex(AuditIntegrityError, "does not extend"):
            verify_signed_export(export, self.signer, "f" * 64)

    def test_rejects_tampered_export_count_and_head(self):
        self.ledger.append("fixture", {})
        export = self.ledger.signed_export(self.signer)
        export["document"]["event_count"] = 2
        with self.assertRaisesRegex(AuditIntegrityError, "count mismatch"):
            verify_signed_export(export, self.signer)


if __name__ == "__main__":
    unittest.main()
