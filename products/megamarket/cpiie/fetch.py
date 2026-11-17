"""Restricted HTTPS fetcher for explicitly allowlisted official policy sources.

No crawling, link discovery, cookies, credentials, or cross-host redirects.
Callers must explicitly allow each source hostname before fetching.
"""
from __future__ import annotations

from dataclasses import dataclass
from email.message import Message
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from . import CPIIERegistry, Document, Source, canonicalize_url


DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_MAX_BYTES = 2 * 1024 * 1024
_ALLOWED_CONTENT_TYPES = {
    "text/html",
    "text/plain",
    "application/xhtml+xml",
    "application/json",
    "application/xml",
    "text/xml",
}


class FetchError(RuntimeError):
    """A source could not be fetched under the configured safety policy."""


@dataclass(frozen=True)
class FetchReceipt:
    source_id: str
    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    byte_count: int
    document: Document


class _SameHostRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old = urlsplit(req.full_url)
        new = urlsplit(newurl)
        if (new.scheme.lower() != "https" or not new.hostname
                or new.hostname.lower() != (old.hostname or "").lower()
                or new.username or new.password):
            raise FetchError("cross-host or non-HTTPS redirect rejected")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class OfficialSourceFetcher:
    """Fetch one registered source URL, only after explicit host allowlisting."""

    def __init__(self, registry: CPIIERegistry, *, timeout: int = DEFAULT_TIMEOUT_SECONDS,
                 max_bytes: int = DEFAULT_MAX_BYTES, opener=None) -> None:
        if timeout <= 0 or max_bytes <= 0:
            raise ValueError("timeout and max_bytes must be positive")
        self.registry = registry
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.opener = opener or build_opener(_SameHostRedirectHandler())

    def fetch(self, source_id: str, *, allowed_hosts: set[str]) -> FetchReceipt:
        row = self.registry.connection.execute(
            "SELECT * FROM sources WHERE source_id=?", (source_id,)
        ).fetchone()
        if not row:
            raise KeyError(f"unknown source: {source_id}")
        source = Source(row["source_id"], row["company_id"], row["role"],
                        row["url"], row["title"])
        url = canonicalize_url(source.url)
        host = urlsplit(url).hostname
        normalized_allowlist = {item.strip().lower().rstrip(".") for item in allowed_hosts}
        if not host or host not in normalized_allowlist:
            raise FetchError("source hostname is not explicitly allowlisted")

        request = Request(url, headers={
            "User-Agent": "MegaMarket-CPIIE-PolicyMonitor/0.1 (+read-only)",
            "Accept": "text/html, text/plain, application/xhtml+xml, application/json, application/xml",
            "Accept-Encoding": "identity",
        }, method="GET")
        try:
            response = self.opener.open(request, timeout=self.timeout)
            with response:
                status = getattr(response, "status", 200)
                if status != 200:
                    raise FetchError(f"unexpected HTTP status: {status}")
                final_url = canonicalize_url(response.geturl())
                if urlsplit(final_url).hostname != host:
                    raise FetchError("response URL escaped the registered source host")
                headers = response.headers
                content_type = headers.get_content_type().lower()
                if content_type not in _ALLOWED_CONTENT_TYPES:
                    raise FetchError(f"unsupported content type: {content_type}")
                length = headers.get("Content-Length")
                if length and int(length) > self.max_bytes:
                    raise FetchError("document exceeds configured size limit")
                payload = response.read(self.max_bytes + 1)
                if len(payload) > self.max_bytes:
                    raise FetchError("document exceeds configured size limit")
                if not payload:
                    raise FetchError("empty source response")
                charset = headers.get_content_charset() or "utf-8"
                try:
                    text = payload.decode(charset, errors="strict")
                except (LookupError, UnicodeDecodeError) as exc:
                    raise FetchError("document is not valid text in its declared charset") from exc
        except HTTPError as exc:
            raise FetchError(f"source returned HTTP {exc.code}") from exc
        except URLError as exc:
            raise FetchError(f"source fetch failed: {exc.reason}") from exc

        document = self.registry.record_document(source_id, text)
        return FetchReceipt(source_id, url, final_url, status, content_type,
                            len(payload), document)
