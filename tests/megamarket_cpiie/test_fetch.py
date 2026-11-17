import unittest
from email.message import Message
from unittest.mock import Mock, patch

from products.megamarket.cpiie import CPIIERegistry, Source
from products.megamarket.cpiie.fetch import FetchError, OfficialSourceFetcher, _SameHostRedirectHandler


class FakeResponse:
    def __init__(self, body=b"<html>official terms</html>",
                 content_type="text/html; charset=utf-8",
                 final_url="https://policy.example.org/terms", status=200):
        self.body = body
        self.status = status
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        self.headers["Content-Length"] = str(len(body))
        self.final_url = final_url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def geturl(self):
        return self.final_url

    def read(self, limit=-1):
        return self.body[:limit]


class OfficialSourceFetcherTests(unittest.TestCase):
    def setUp(self):
        self.registry = CPIIERegistry()
        self.registry.register_source(Source(
            "policy", "company-a", "affiliate-terms",
            "https://policy.example.org/terms", "Affiliate terms",
        ))
        self.opener = Mock()
        self.fetcher = OfficialSourceFetcher(
            self.registry, opener=self.opener, max_bytes=1024
        )

    def tearDown(self):
        self.registry.close()

    def test_fetch_requires_explicit_host_allowlist(self):
        with self.assertRaises(FetchError):
            self.fetcher.fetch("policy", allowed_hosts=set())
        self.opener.open.assert_not_called()

    def test_fetch_records_snapshot_and_receipt(self):
        self.opener.open.return_value = FakeResponse()
        receipt = self.fetcher.fetch(
            "policy", allowed_hosts={"policy.example.org"}
        )
        self.assertEqual(receipt.status_code, 200)
        self.assertEqual(receipt.content_type, "text/html")
        self.assertEqual(receipt.document.version, 1)
        self.assertEqual(receipt.document.content_sha256,
                         self.registry.connection.execute(
                             "SELECT content_sha256 FROM documents"
                         ).fetchone()[0])
        self.opener.open.assert_called_once()

    def test_fetch_does_not_create_new_version_for_identical_content(self):
        self.opener.open.return_value = FakeResponse()
        first = self.fetcher.fetch("policy", allowed_hosts={"policy.example.org"})
        second = self.fetcher.fetch("policy", allowed_hosts={"policy.example.org"})
        self.assertEqual(first.document.document_id, second.document.document_id)
        self.assertEqual(second.document.version, 1)
        self.assertFalse(second.document.changed)

    def test_oversized_content_length_is_rejected_before_read(self):
        response = FakeResponse()
        response.headers["Content-Length"] = "999999"
        self.opener.open.return_value = response
        with self.assertRaises(FetchError):
            self.fetcher.fetch("policy", allowed_hosts={"policy.example.org"})

    def test_oversized_body_is_rejected(self):
        self.opener.open.return_value = FakeResponse(body=b"x" * 2048)
        with self.assertRaises(FetchError):
            self.fetcher.fetch("policy", allowed_hosts={"policy.example.org"})

    def test_unsupported_content_type_is_rejected(self):
        self.opener.open.return_value = FakeResponse(content_type="application/pdf")
        with self.assertRaises(FetchError):
            self.fetcher.fetch("policy", allowed_hosts={"policy.example.org"})

    def test_cross_host_response_url_is_rejected(self):
        self.opener.open.return_value = FakeResponse(
            final_url="https://other.example.net/terms"
        )
        with self.assertRaises(FetchError):
            self.fetcher.fetch("policy", allowed_hosts={"policy.example.org"})

    def test_invalid_text_encoding_is_rejected(self):
        self.opener.open.return_value = FakeResponse(
            body=b"\xff\xfe", content_type="text/html; charset=utf-8"
        )
        with self.assertRaises(FetchError):
            self.fetcher.fetch("policy", allowed_hosts={"policy.example.org"})

    def test_redirect_handler_rejects_cross_host_and_http(self):
        handler = _SameHostRedirectHandler()
        request = Mock()
        request.full_url = "https://policy.example.org/terms"
        with self.assertRaises(FetchError):
            handler.redirect_request(
                request, None, 302, "Found", {}, "https://attacker.example.net/collect"
            )
        with self.assertRaises(FetchError):
            handler.redirect_request(
                request, None, 302, "Found", {}, "http://policy.example.org/terms"
            )

    def test_unknown_source_is_rejected(self):
        with self.assertRaises(KeyError):
            self.fetcher.fetch("missing", allowed_hosts={"policy.example.org"})

    def test_dns_resolution_rejects_private_addresses(self):
        private_answer = (None, None, None, None, ("10.0.0.8", 443))
        with patch("products.megamarket.cpiie.fetch.socket.getaddrinfo",
                   return_value=[private_answer]):
            with self.assertRaises(FetchError):
                OfficialSourceFetcher._resolve_public_ip("policy.example.org")

    def test_dns_resolution_pins_public_address(self):
        public_answer = (None, None, None, None, ("8.8.8.8", 443))
        with patch("products.megamarket.cpiie.fetch.socket.getaddrinfo",
                   return_value=[public_answer]):
            self.assertEqual(
                OfficialSourceFetcher._resolve_public_ip("policy.example.org"),
                "8.8.8.8",
            )

    def test_redirect_handler_rejects_port_change(self):
        handler = _SameHostRedirectHandler()
        request = Mock()
        request.full_url = "https://policy.example.org/terms"
        with self.assertRaises(FetchError):
            handler.redirect_request(
                request, None, 302, "Found", {},
                "https://policy.example.org:8443/terms",
            )


if __name__ == "__main__":
    unittest.main()
