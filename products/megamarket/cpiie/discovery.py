"""Bounded, same-origin discovery of candidate policy-document links.

This module does not fetch pages, register sources, or decide that a link is
authoritative. It only ranks links found in one caller-supplied HTML document.
"""
from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from . import canonicalize_url


_ROLE_TERMS = {
    "terms": ("terms", "conditions", "legal"),
    "affiliate-terms": ("affiliate", "partner", "publisher"),
    "api-docs": ("api", "developer", "documentation", "docs"),
    "feed-specification": ("feed", "product data", "catalog"),
    "brand-guidelines": ("brand", "trademark", "logo", "press"),
    "privacy-policy": ("privacy", "cookie", "tracking"),
    "disclosure-policy": ("disclosure", "advertising", "endorsement"),
    "country-restrictions": ("country", "territory", "region", "availability"),
    "support": ("support", "contact", "help"),
}
_MAX_CANDIDATES = 100


@dataclass(frozen=True)
class SourceCandidate:
    url: str
    title: str
    suggested_roles: tuple[str, ...]
    matched_terms: tuple[str, ...]


class _AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self._href = None
        self._parts = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._parts = []

    def handle_data(self, data):
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.links.append((self._href, " ".join(" ".join(self._parts).split())))
            self._href = None
            self._parts = []


def discover_candidates(html: str, page_url: str, *, max_candidates: int = 50) -> tuple[SourceCandidate, ...]:
    """Return bounded same-origin candidates; never fetch or auto-register them."""
    if not isinstance(html, str) or not html.strip():
        raise ValueError("HTML input must not be empty")
    if not 1 <= max_candidates <= _MAX_CANDIDATES:
        raise ValueError(f"max_candidates must be between 1 and {_MAX_CANDIDATES}")
    base = canonicalize_url(page_url)
    base_parts = urlsplit(base)
    parser = _AnchorParser()
    parser.feed(html)
    found = {}
    for href, title in parser.links:
        if not href:
            continue
        try:
            candidate_url = canonicalize_url(urljoin(base, href))
        except ValueError:
            continue
        parts = urlsplit(candidate_url)
        if parts.hostname != base_parts.hostname or parts.port != base_parts.port:
            continue
        searchable = f"{candidate_url} {title}".lower()
        roles, terms = [], []
        for role, keywords in _ROLE_TERMS.items():
            matches = [term for term in keywords if term in searchable]
            if matches:
                roles.append(role)
                terms.extend(matches)
        if not roles:
            continue
        existing = found.get(candidate_url)
        candidate = SourceCandidate(candidate_url, title or candidate_url,
                                     tuple(roles), tuple(sorted(set(terms))))
        if existing is None or len(candidate.suggested_roles) > len(existing.suggested_roles):
            found[candidate_url] = candidate
        if len(found) >= max_candidates:
            break
    return tuple(found[url] for url in sorted(found))
