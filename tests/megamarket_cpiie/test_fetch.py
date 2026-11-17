import http.server
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import unittest
from email.message import Message
from unittest.mock import Mock, patch

from products.megamarket.cpiie import CPIIERegistry, Source
from products.megamarket.cpiie.fetch import (
    FetchError,
    OfficialSourceFetcher,
    _PinnedHTTPSConnection,
    _SameHostRedirectHandler,
)


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

    def test_fetch_rejects_allowlist_suffix_spoof(self):
        with self.assertRaises(FetchError):
            self.fetcher.fetch(
                "policy", allowed_hosts={"policy.example.org.attacker.invalid"}
            )
        self.opener.open.assert_not_called()

    def test_read_timeout_is_normalized_to_fetch_error(self):
        class TimeoutResponse(FakeResponse):
            def read(self, limit=-1):
                raise TimeoutError("simulated socket read timeout")

        self.opener.open.return_value = TimeoutResponse()
        with self.assertRaisesRegex(FetchError, "response read failed"):
            self.fetcher.fetch(
                "policy", allowed_hosts={"policy.example.org"}
            )

    def test_read_oserror_is_normalized_to_fetch_error(self):
        class BrokenResponse(FakeResponse):
            def read(self, limit=-1):
                raise OSError("simulated connection reset")

        self.opener.open.return_value = BrokenResponse()
        with self.assertRaisesRegex(FetchError, "response read failed"):
            self.fetcher.fetch(
                "policy", allowed_hosts={"policy.example.org"}
            )


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

    def test_negative_content_length_is_rejected(self):
        response = FakeResponse()
        response.headers["Content-Length"] = "-1"
        self.opener.open.return_value = response
        with self.assertRaisesRegex(FetchError, "Content-Length"):
            self.fetcher.fetch("policy", allowed_hosts={"policy.example.org"})

    def test_conflicting_content_lengths_are_rejected(self):
        response = FakeResponse()
        response.headers.add_header("Content-Length", "999")
        self.opener.open.return_value = response
        with self.assertRaisesRegex(FetchError, "Content-Length"):
            self.fetcher.fetch("policy", allowed_hosts={"policy.example.org"})

    def test_invalid_redirect_port_is_rejected_as_fetch_error(self):
        handler = _SameHostRedirectHandler()
        request = Mock()
        request.full_url = "https://policy.example.org/terms"
        with self.assertRaisesRegex(FetchError, "invalid port"):
            handler.redirect_request(
                request, None, 302, "Found", {},
                "https://policy.example.org:not-a-port/terms",
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

    def test_dns_resolution_rejects_mixed_public_and_private_answers(self):
        public_answer = (None, None, None, None, ("8.8.8.8", 443))
        private_answer = (None, None, None, None, ("192.168.1.10", 443))
        with patch("products.megamarket.cpiie.fetch.socket.getaddrinfo",
                   return_value=[public_answer, private_answer]):
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

    def test_pinned_https_connection_uses_ip_but_preserves_hostname_sni(self):
        raw_socket = Mock(name="raw_socket")
        tls_socket = Mock(name="tls_socket")
        tls_context = Mock(name="tls_context")
        tls_context.wrap_socket.return_value = tls_socket
        with patch(
            "products.megamarket.cpiie.fetch.socket.create_connection",
            return_value=raw_socket,
        ) as create_connection:
            connection = _PinnedHTTPSConnection(
                "policy.example.org",
                "8.8.8.8",
                timeout=7,
                context=tls_context,
            )
            connection.connect()

        create_connection.assert_called_once_with(
            ("8.8.8.8", 443), 7, None
        )
        tls_context.wrap_socket.assert_called_once_with(
            raw_socket, server_hostname="policy.example.org"
        )
        self.assertIs(connection.sock, tls_socket)

    def test_pinned_https_connection_keeps_default_certificate_verification(self):
        connection = _PinnedHTTPSConnection(
            "policy.example.org", "8.8.8.8"
        )
        self.assertTrue(connection._context.check_hostname)
        self.assertEqual(connection._context.verify_mode, ssl.CERT_REQUIRED)

    def test_redirect_handler_rejects_port_change(self):
        handler = _SameHostRedirectHandler()
        request = Mock()
        request.full_url = "https://policy.example.org/terms"
        with self.assertRaises(FetchError):
            handler.redirect_request(
                request, None, 302, "Found", {},
                "https://policy.example.org:8443/terms",
            )

    def test_redirect_handler_rejects_userinfo_and_host_suffix_spoof(self):
        handler = _SameHostRedirectHandler()
        request = Mock()
        request.full_url = "https://policy.example.org/terms"
        for target in (
            "https://user@policy.example.org/terms",
            "https://policy.example.org.attacker.invalid/terms",
        ):
            with self.subTest(target=target):
                with self.assertRaises(FetchError):
                    handler.redirect_request(
                        request, None, 302, "Found", {}, target
                    )


    def _run_real_tls_fetch(self, hostname, *, trust_certificate):
        if not shutil.which("openssl"):
            self.skipTest("OpenSSL CLI is required for local TLS integration tests")

        with tempfile.TemporaryDirectory() as directory:
            cert_path = f"{directory}/server-cert.pem"
            key_path = f"{directory}/server-key.pem"
            subprocess.run(
                [
                    "openssl", "req", "-x509", "-newkey", "rsa:2048",
                    "-nodes", "-keyout", key_path, "-out", cert_path,
                    "-days", "365", "-subj", "/CN=policy.example.org",
                    "-addext", "subjectAltName=DNS:policy.example.org",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            class Handler(http.server.BaseHTTPRequestHandler):
                def do_GET(self):
                    body = b"<html>verified TLS policy</html>"
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

                def log_message(self, *args):
                    pass

            server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            server_context.load_cert_chain(certfile=cert_path, keyfile=key_path)
            server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
            server.socket = server_context.wrap_socket(server.socket, server_side=True)
            port = server.server_address[1]
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            source_id = f"tls-{hostname}"
            self.registry.register_source(Source(
                source_id, "company-a", "affiliate-terms",
                f"https://{hostname}/tls/{source_id}/terms", "TLS integration fixture",
            ))

            client_context = (
                ssl.create_default_context(cafile=cert_path)
                if trust_certificate
                else ssl.create_default_context()
            )
            self.assertTrue(client_context.check_hostname)
            self.assertEqual(client_context.verify_mode, ssl.CERT_REQUIRED)

            original_getaddrinfo = socket.getaddrinfo
            original_create_connection = socket.create_connection
            pinned_destinations = []

            def fake_getaddrinfo(host, *args, **kwargs):
                if host == hostname:
                    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "",
                             ("8.8.8.8", 443))]
                return original_getaddrinfo(host, *args, **kwargs)

            def route_pinned_ip_to_local_server(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT,
                                                source_address=None, **kwargs):
                host, target_port = address
                if host == "8.8.8.8":
                    pinned_destinations.append(host)
                    address = ("127.0.0.1", port)
                return original_create_connection(
                    address, timeout, source_address, **kwargs
                )

            try:
                with (
                    patch(
                        "products.megamarket.cpiie.fetch.socket.getaddrinfo",
                        side_effect=fake_getaddrinfo,
                    ),
                    patch(
                        "products.megamarket.cpiie.fetch.socket.create_connection",
                        side_effect=route_pinned_ip_to_local_server,
                    ),
                    patch(
                        "ssl._create_default_https_context",
                        return_value=client_context,
                    ),
                ):
                    receipt = OfficialSourceFetcher(
                        self.registry, timeout=3, max_bytes=1024
                    ).fetch(source_id, allowed_hosts={hostname})
                self.assertEqual(pinned_destinations, ["8.8.8.8"])
                return receipt
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_real_https_accepts_trusted_certificate_and_matching_hostname(self):
        receipt = self._run_real_tls_fetch(
            "policy.example.org", trust_certificate=True
        )
        self.assertEqual(receipt.status_code, 200)
        self.assertIn("verified TLS policy", self.registry.connection.execute("SELECT content FROM documents WHERE document_id=?", (receipt.document.document_id,)).fetchone()[0])

    def test_real_https_rejects_untrusted_certificate_authority(self):
        with self.assertRaises(FetchError):
            self._run_real_tls_fetch(
                "policy.example.org", trust_certificate=False
            )

    def test_real_https_rejects_certificate_hostname_mismatch(self):
        with self.assertRaises(FetchError):
            self._run_real_tls_fetch(
                "wrong.example.org", trust_certificate=True
            )


if __name__ == "__main__":
    unittest.main()
