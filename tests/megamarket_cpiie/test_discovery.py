import unittest

from products.megamarket.cpiie.discovery import discover_candidates


class DiscoveryTests(unittest.TestCase):
    def test_discovers_same_origin_policy_candidates_only(self):
        html = """
        <a href="/legal/terms">Terms and Conditions</a>
        <a href="/partners/affiliate">Affiliate program</a>
        <a href="https://external.example.net/privacy">Privacy policy</a>
        <a href="mailto:legal@example.org">Contact legal</a>
        <a href="/ordinary-page">About our company</a>
        """
        results = discover_candidates(html, "https://shop.example.org/")
        urls = {item.url for item in results}
        self.assertIn("https://shop.example.org/legal/terms", urls)
        self.assertIn("https://shop.example.org/partners/affiliate", urls)
        self.assertFalse(any("external.example.net" in url for url in urls))
        affiliate = next(item for item in results if item.url.endswith("/affiliate"))
        self.assertIn("affiliate-terms", affiliate.suggested_roles)

    def test_discovery_is_bounded(self):
        html = "".join(
            f'<a href="/legal/terms-{i}">Terms {i}</a>' for i in range(10)
        )
        self.assertLessEqual(
            len(discover_candidates(html, "https://shop.example.org/", max_candidates=3)),
            3,
        )

    def test_rejects_invalid_limits(self):
        with self.assertRaises(ValueError):
            discover_candidates("<a href='/terms'>Terms</a>",
                                "https://shop.example.org/", max_candidates=0)

    def test_empty_html_is_rejected(self):
        with self.assertRaises(ValueError):
            discover_candidates(" ", "https://shop.example.org/")


if __name__ == "__main__":
    unittest.main()
