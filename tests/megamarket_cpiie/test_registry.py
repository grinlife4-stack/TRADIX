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


if __name__ == "__main__":
    unittest.main()
