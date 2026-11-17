import sqlite3
import tempfile
import unittest

from products.megamarket.cpiie import (
    CPIIERegistry, CapabilityState, PolicyEffect, RuleState, Source, canonicalize_url,
)


class CPIIERegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = CPIIERegistry()
        self.registry.register_source(Source(
            "retailer-terms", "retailer-x", "retailer",
            "https://EXAMPLE.com/terms#section", "Official terms",
        ))
        self.doc = self.registry.record_document("retailer-terms", "Terms v1\nProduct data may be displayed.")
        self.evidence = self.registry.record_evidence(
            self.doc.document_id, "section 4", "Product data may be displayed."
        )

    def tearDown(self):
        self.registry.close()

    def propose(self, rule_id="rule-1", capability="catalog.display"):
        return self.registry.propose_rule(
            rule_id, self.doc.document_id, self.evidence,
            capability, "Display product data only under the cited terms.",
            effect=PolicyEffect.ALLOW,
        )

    def test_https_url_is_canonicalized(self):
        self.assertEqual(
            canonicalize_url("HTTPS://Example.COM:443/a#b"),
            "https://example.com/a",
        )

    def test_non_https_source_is_rejected(self):
        with self.assertRaises(ValueError):
            canonicalize_url("http://example.com/terms")

    def test_evidence_excerpt_must_exist_in_exact_document_snapshot(self):
        with self.assertRaisesRegex(ValueError, "must appear"):
            self.registry.record_evidence(
                self.doc.document_id, "section 99", "Fabricated permission text"
            )

    def test_document_snapshots_are_immutable_at_database_layer(self):
        with self.assertRaisesRegex(Exception, "document snapshots are immutable"):
            self.registry.connection.execute(
                "UPDATE documents SET content='tampered' WHERE document_id=?",
                (self.doc.document_id,),
            )
        self.registry.connection.rollback()
        with self.assertRaisesRegex(Exception, "document snapshots are immutable"):
            self.registry.connection.execute(
                "DELETE FROM documents WHERE document_id=?", (self.doc.document_id,)
            )
        self.registry.connection.rollback()
        row = self.registry.connection.execute(
            "SELECT content FROM documents WHERE document_id=?", (self.doc.document_id,)
        ).fetchone()
        self.assertIn("Product data may be displayed.", row["content"])

    def test_evidence_records_are_immutable_at_database_layer(self):
        with self.assertRaisesRegex(Exception, "evidence records are immutable"):
            self.registry.connection.execute(
                "UPDATE evidence SET excerpt='tampered' WHERE evidence_id=?",
                (self.evidence,),
            )
        self.registry.connection.rollback()
        with self.assertRaisesRegex(Exception, "evidence records are immutable"):
            self.registry.connection.execute(
                "DELETE FROM evidence WHERE evidence_id=?", (self.evidence,)
            )
        self.registry.connection.rollback()

    def test_rule_review_is_audited_by_database_trigger(self):
        self.propose()
        self.registry.connection.execute(
            "UPDATE rules SET state='VERIFIED', reviewer='direct-reviewer', "
            "reviewed_at='2026-11-17T12:00:00+00:00' WHERE rule_id='rule-1'"
        )
        self.registry.connection.commit()
        history = self.registry.get_review_history("rule-1")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["previous_state"], "NEEDS_REVIEW")
        self.assertEqual(history[0]["decision"], "VERIFIED")
        self.assertEqual(history[0]["reviewer"], "direct-reviewer")

    def test_rule_content_cannot_be_changed_after_proposal(self):
        self.propose()
        with self.assertRaisesRegex(Exception, "rule content is immutable"):
            self.registry.connection.execute(
                "UPDATE rules SET statement='tampered' WHERE rule_id='rule-1'"
            )
        self.registry.connection.rollback()
        with self.assertRaisesRegex(Exception, "rule records are append-only"):
            self.registry.connection.execute("DELETE FROM rules WHERE rule_id='rule-1'")
        self.registry.connection.rollback()

    def test_rule_expiry_requires_timezone_aware_iso_timestamp(self):
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            self.registry.propose_rule(
                "bad-expiry", self.doc.document_id, self.evidence,
                "catalog.display", "Temporary policy", "not-a-date",
            )
        with self.assertRaisesRegex(ValueError, "timezone offset"):
            self.registry.propose_rule(
                "naive-expiry", self.doc.document_id, self.evidence,
                "catalog.display", "Temporary policy", "2030-01-01T00:00:00",
            )

    def test_document_timestamp_requires_timezone(self):
        with self.assertRaisesRegex(ValueError, "timezone offset"):
            self.registry.record_document(
                "retailer-terms", "Terms with naive time", "2026-11-17T12:00:00"
            )

    def test_document_hash_and_duplicate_are_deterministic(self):
        first = self.doc
        duplicate = self.registry.record_document("retailer-terms", "Terms v1\nProduct data may be displayed.")
        self.assertEqual(first.content_sha256, duplicate.content_sha256)
        self.assertFalse(duplicate.changed)
        self.assertEqual(first.version, duplicate.version)

    def test_changed_document_increments_version(self):
        changed = self.registry.record_document("retailer-terms", "Terms v2")
        self.assertEqual(changed.version, 2)
        self.assertTrue(changed.changed)

    def test_rule_defaults_to_needs_review(self):
        self.assertEqual(self.propose().state, RuleState.NEEDS_REVIEW)
        self.assertEqual(
            self.registry.evaluate("catalog.display").state,
            CapabilityState.BLOCKED_REVIEW,
        )

    def test_duplicate_rule_id_is_idempotent_only_for_identical_content(self):
        first = self.propose()
        same = self.propose()
        self.assertEqual(first, same)
        with self.assertRaisesRegex(ValueError, "different rule content"):
            self.registry.propose_rule(
                "rule-1", self.doc.document_id, self.evidence,
                "catalog.display", "A different statement under the same ID.",
            )
        self.assertEqual(self.registry.get_rule("rule-1"), first)

    def test_rule_cannot_be_verified_without_reviewer(self):
        self.propose()
        with self.assertRaises(ValueError):
            self.registry.review_rule("rule-1", "", RuleState.VERIFIED)

    def test_verified_rule_without_explicit_effect_remains_blocked(self):
        self.registry.propose_rule(
            "unspecified-rule", self.doc.document_id, self.evidence,
            "catalog.unspecified", "A statement without a structured effect.",
        )
        self.registry.review_rule("unspecified-rule", "reviewer", RuleState.VERIFIED)
        result = self.registry.evaluate("catalog.unspecified")
        self.assertEqual(result.state, CapabilityState.BLOCKED_REVIEW)
        self.assertIn("lack an explicit", result.reason)

    def test_explicit_deny_blocks_even_when_other_rule_allows(self):
        self.propose("allow-rule", "catalog.mixed")
        self.registry.review_rule("allow-rule", "reviewer-a", RuleState.VERIFIED)
        self.registry.propose_rule(
            "deny-rule", self.doc.document_id, self.evidence,
            "catalog.mixed", "Do not display product data.",
            effect=PolicyEffect.DENY,
        )
        self.registry.review_rule("deny-rule", "reviewer-b", RuleState.VERIFIED)
        result = self.registry.evaluate("catalog.mixed")
        self.assertEqual(result.state, CapabilityState.BLOCKED_POLICY_DENY)
        self.assertIn("explicitly denies", result.reason)

    def test_legacy_database_migrates_missing_effect_to_unspecified(self):
        with tempfile.NamedTemporaryFile(suffix=".sqlite3") as database:
            connection = sqlite3.connect(database.name)
            connection.execute("""
                CREATE TABLE rules (
                    rule_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    evidence_id TEXT NOT NULL,
                    capability TEXT NOT NULL,
                    statement TEXT NOT NULL,
                    state TEXT NOT NULL,
                    expires_at TEXT,
                    reviewer TEXT,
                    reviewed_at TEXT
                )
            """)
            connection.execute(\n                "INSERT INTO rules VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",\n                ("legacy-rule", "legacy-doc", "legacy-evidence", "legacy.cap",\n                 "Legacy policy", "VERIFIED", None, "legacy reviewer",\n                 "2026-11-17T00:00:00+00:00"),\n            )\n            connection.commit()\n            connection.close()\n\n            migrated = CPIIERegistry(database.name)
            try:
                columns = {
                    row["name"] for row in migrated.connection.execute("PRAGMA table_info(rules)")
                }
                self.assertIn("effect", columns)
                self.assertEqual(migrated.get_rule("legacy-rule").effect, PolicyEffect.UNSPECIFIED)
            finally:
                migrated.close()

    def test_invalid_policy_effect_is_rejected_by_database_guard(self):
        with self.assertRaises(ValueError):
            self.registry.propose_rule(
                "invalid-effect", self.doc.document_id, self.evidence,
                "catalog.invalid", "Invalid effect",
                effect="MAYBE",
            )

    def test_policy_effect_is_immutable(self):
        self.propose()
        with self.assertRaisesRegex(Exception, "rule content is immutable"):
            self.registry.connection.execute(
                "UPDATE rules SET effect='DENY' WHERE rule_id='rule-1'"
            )
        self.registry.connection.rollback()
        self.assertEqual(self.registry.get_rule("rule-1").effect, PolicyEffect.ALLOW)

    def test_verified_rule_allows_its_capability(self):
        self.propose()
        self.registry.review_rule("rule-1", "human-reviewer", RuleState.VERIFIED)
        self.assertEqual(
            self.registry.evaluate("catalog.display").state,
            CapabilityState.ALLOWED,
        )

    def test_newer_source_snapshot_invalidates_old_policy_approval(self):
        self.propose()
        self.registry.review_rule("rule-1", "human-reviewer", RuleState.VERIFIED)
        self.assertEqual(
            self.registry.evaluate("catalog.display").state,
            CapabilityState.ALLOWED,
        )

        self.registry.record_document("retailer-terms", "Terms v2")
        result = self.registry.evaluate("catalog.display")
        self.assertEqual(result.state, CapabilityState.BLOCKED_REVIEW)
        self.assertIn("newer source snapshot", result.reason)

    def test_source_url_change_requires_new_source_id(self):
        with self.assertRaisesRegex(ValueError, "source identity is immutable"):
            self.registry.register_source(Source(
                "retailer-terms", "retailer-x", "retailer",
                "https://example.com/new-terms", "New terms",
            ))
        self.assertEqual(
            self.registry.record_document("retailer-terms", "Terms v2").version, 2
        )

    def test_source_identity_is_immutable_at_database_layer(self):
        with self.assertRaisesRegex(Exception, "source identity is immutable"):
            self.registry.connection.execute(
                "UPDATE sources SET url='https://example.com/changed' "
                "WHERE source_id='retailer-terms'"
            )
        self.registry.connection.rollback()
        source = self.registry.connection.execute(
            "SELECT url FROM sources WHERE source_id='retailer-terms'"
        ).fetchone()
        self.assertEqual(source["url"], "https://example.com/terms")

    def test_source_company_and_role_are_immutable(self):
        for company_id, role in (("other-company", "retailer"),
                                 ("retailer-x", "affiliate-policy")):
            with self.subTest(company_id=company_id, role=role):
                with self.assertRaisesRegex(ValueError, "source identity is immutable"):
                    self.registry.register_source(Source(
                        "retailer-terms", company_id, role,
                        "https://example.com/terms", "Official terms",
                    ))

    def test_source_title_can_be_refreshed_without_changing_identity(self):
        updated = self.registry.register_source(Source(
            "retailer-terms", "retailer-x", "retailer",
            "https://example.com/terms", "Updated display title",
        ))
        self.assertEqual(updated.title, "Updated display title")
        self.assertEqual(
            self.registry.evaluate("catalog.display").state,
            CapabilityState.BLOCKED_NO_POLICY,
        )

    def test_review_history_records_each_decision_in_order(self):
        self.propose()
        self.registry.review_rule("rule-1", " reviewer-a ", RuleState.VERIFIED)
        self.registry.review_rule("rule-1", "reviewer-b", RuleState.CONFLICT)
        history = self.registry.get_review_history("rule-1")
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["previous_state"], RuleState.NEEDS_REVIEW.value)
        self.assertEqual(history[0]["decision"], RuleState.VERIFIED.value)
        self.assertEqual(history[0]["reviewer"], "reviewer-a")
        self.assertEqual(history[1]["previous_state"], RuleState.VERIFIED.value)
        self.assertEqual(history[1]["decision"], RuleState.CONFLICT.value)
        self.assertEqual(history[1]["reviewer"], "reviewer-b")

    def test_review_history_is_append_only(self):
        self.propose()
        self.registry.review_rule("rule-1", "reviewer", RuleState.VERIFIED)
        with self.assertRaisesRegex(Exception, "append-only"):
            self.registry.connection.execute(
                "UPDATE rule_review_history SET reviewer='tampered' WHERE rule_id='rule-1'"
            )
        with self.assertRaisesRegex(Exception, "append-only"):
            self.registry.connection.execute(
                "DELETE FROM rule_review_history WHERE rule_id='rule-1'"
            )
        self.registry.connection.rollback()
        self.assertEqual(
            self.registry.get_review_history("rule-1")[0]["reviewer"], "reviewer"
        )

    def test_review_history_is_included_in_audit_snapshot(self):
        self.propose()
        self.registry.review_rule("rule-1", "reviewer", RuleState.VERIFIED)
        snapshot = self.registry.export_snapshot()
        self.assertIn('"rule_review_history"', snapshot)
        self.assertIn('"reviewer"', snapshot)

    def test_conflict_blocks_capability(self):
        self.propose()
        self.registry.review_rule("rule-1", "human-reviewer", RuleState.CONFLICT)
        self.assertEqual(
            self.registry.evaluate("catalog.display").state,
            CapabilityState.BLOCKED_CONFLICT,
        )

    def test_expired_rule_blocks_capability(self):
        self.registry.propose_rule(
            "rule-exp", self.doc.document_id, self.evidence,
            "catalog.display", "Temporary permission", "2020-01-01T00:00:00+00:00",
        )
        self.registry.review_rule("rule-exp", "human-reviewer", RuleState.VERIFIED)
        self.assertEqual(
            self.registry.evaluate("catalog.display").state,
            CapabilityState.BLOCKED_EXPIRED,
        )

    def test_unknown_capability_fails_closed(self):
        self.assertEqual(
            self.registry.evaluate("unknown.capability").state,
            CapabilityState.BLOCKED_NO_POLICY,
        )

    def test_evidence_must_belong_to_document(self):
        other = self.registry.record_document("retailer-terms", "Terms v2")
        with self.assertRaises(ValueError):
            self.registry.propose_rule(
                "bad-rule", other.document_id, self.evidence,
                "catalog.display", "Mismatched evidence",
            )

    def test_snapshot_is_deterministic(self):
        self.propose()
        self.assertEqual(
            self.registry.export_snapshot(), self.registry.export_snapshot()
        )

    def test_stale_source_snapshot_blocks_capability(self):
        old_registry = CPIIERegistry()
        try:
            old_registry.register_source(Source(
                "old-source", "retailer-x", "retailer",
                "https://example.org/old-terms", "Old terms",
            ))
            old_doc = old_registry.record_document(
                "old-source", "Old terms", "2020-01-01T00:00:00+00:00"
            )
            evidence = old_registry.record_evidence(old_doc.document_id, "s1", "Old terms")
            old_registry.propose_rule(
                "old-rule", old_doc.document_id, evidence,
                "catalog.old", "Old permission",
            )
            old_registry.review_rule("old-rule", "reviewer", RuleState.VERIFIED)
            result = old_registry.evaluate(
                "catalog.old", now="2026-11-17T00:00:00+00:00",
                max_age_seconds=86400,
            )
            self.assertEqual(result.state, CapabilityState.BLOCKED_EXPIRED)
            self.assertIn("stale", result.reason)
        finally:
            old_registry.close()

    def test_audit_snapshot_does_not_export_document_body(self):
        self.propose()
        snapshot = self.registry.export_snapshot()
        self.assertNotIn('"content"', snapshot)
        self.assertNotIn("Terms v1", snapshot)

    def test_ip_literal_source_is_rejected(self):
        with self.assertRaises(ValueError):
            canonicalize_url("https://127.0.0.1/terms")

    def test_local_hostname_source_is_rejected(self):
        with self.assertRaises(ValueError):
            canonicalize_url("https://service.internal/terms")

    def test_nonstandard_https_port_is_rejected(self):
        with self.assertRaises(ValueError):
            canonicalize_url("https://example.com:8443/terms")


if __name__ == "__main__":
    unittest.main()
