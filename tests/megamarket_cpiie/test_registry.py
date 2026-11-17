import unittest

from products.megamarket.cpiie import (
    CPIIERegistry, CapabilityState, RuleState, Source, canonicalize_url,
)


class CPIIERegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = CPIIERegistry()
        self.registry.register_source(Source(
            "retailer-terms", "retailer-x", "retailer",
            "https://EXAMPLE.com/terms#section", "Official terms",
        ))
        self.doc = self.registry.record_document("retailer-terms", "Terms v1")
        self.evidence = self.registry.record_evidence(
            self.doc.document_id, "section 4", "Product data may be displayed."
        )

    def tearDown(self):
        self.registry.close()

    def propose(self, rule_id="rule-1", capability="catalog.display"):
        return self.registry.propose_rule(
            rule_id, self.doc.document_id, self.evidence,
            capability, "Display product data only under the cited terms.",
        )

    def test_https_url_is_canonicalized(self):
        self.assertEqual(
            canonicalize_url("HTTPS://Example.COM:443/a#b"),
            "https://example.com/a",
        )

    def test_non_https_source_is_rejected(self):
        with self.assertRaises(ValueError):
            canonicalize_url("http://example.com/terms")

    def test_document_hash_and_duplicate_are_deterministic(self):
        first = self.doc
        duplicate = self.registry.record_document("retailer-terms", "Terms v1")
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
            evidence = old_registry.record_evidence(old_doc.document_id, "s1", "Old excerpt")
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
