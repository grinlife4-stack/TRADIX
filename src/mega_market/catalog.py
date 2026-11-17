"""Permission-gated, source-neutral market listing ingestion and conservative matching."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
import unicodedata
from typing import Iterable, Literal, Protocol

from .economics import Money


AccessMode = Literal["public_api", "licensed_api", "manual_import"]
PermissionStatus = Literal["approved", "pending", "blocked"]
Availability = Literal["in_stock", "out_of_stock", "unknown"]
Condition = Literal["new", "used", "refurbished", "unknown"]

_MARKET_CODE = re.compile(r"^[A-Z]{2}$")
_GTIN_LENGTHS = {8, 12, 13, 14}


class SourcePermissionError(ValueError):
    """Raised when a data source is not approved for use."""


@dataclass(frozen=True, slots=True)
class SourceDescriptor:
    source_id: str
    display_name: str
    access_mode: AccessMode
    permission_status: PermissionStatus
    permission_reference: str | None
    terms_reviewed_at: datetime | None

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.display_name.strip():
            raise ValueError("source identity fields cannot be empty")
        if self.permission_status == "approved":
            if not self.permission_reference or not self.permission_reference.strip():
                raise ValueError("approved sources require a permission reference")
            if self.terms_reviewed_at is None:
                raise ValueError("approved sources require a terms review timestamp")
            if self.terms_reviewed_at.tzinfo is None or self.terms_reviewed_at.utcoffset() is None:
                raise ValueError("terms_reviewed_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class ListingObservation:
    source_id: str
    source_record_id: str
    observed_at: datetime
    title: str
    price: Money
    market_code: str
    brand: str | None = None
    manufacturer_part_number: str | None = None
    gtin: str | None = None
    variant: str | None = None
    availability: Availability = "unknown"
    condition: Condition = "unknown"
    product_url: str | None = None
    category: str | None = None

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.source_record_id.strip():
            raise ValueError("source and source record identifiers cannot be empty")
        if not self.title.strip():
            raise ValueError("listing title cannot be empty")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        if not _MARKET_CODE.fullmatch(self.market_code):
            raise ValueError("market_code must be an uppercase two-letter code")
        if self.price.amount <= 0:
            raise ValueError("listing price must be greater than zero")


class MarketDataAdapter(Protocol):
    @property
    def descriptor(self) -> SourceDescriptor: ...

    def fetch_listings(
        self,
        query: str,
        market_code: str,
        limit: int,
    ) -> Iterable[ListingObservation]: ...


@dataclass(frozen=True, slots=True)
class SourceFailure:
    source_id: str
    error_type: str
    message: str


@dataclass(frozen=True, slots=True)
class IngestionReport:
    requested_sources: tuple[str, ...]
    observations: tuple[ListingObservation, ...]
    failures: tuple[SourceFailure, ...]
    duplicate_source_records: int

    @property
    def complete(self) -> bool:
        return not self.failures


@dataclass(frozen=True, slots=True)
class ProductCluster:
    identity_key: str
    listings: tuple[ListingObservation, ...]


class SourceRegistry:
    """In-memory registry. Persistent credentials and network clients are out of scope."""

    def __init__(self) -> None:
        self._adapters: dict[str, MarketDataAdapter] = {}

    def register(self, adapter: MarketDataAdapter) -> None:
        descriptor = adapter.descriptor
        if descriptor.permission_status != "approved":
            raise SourcePermissionError(
                f"source {descriptor.source_id} is not approved for data access"
            )
        if descriptor.source_id in self._adapters:
            raise ValueError(f"source already registered: {descriptor.source_id}")
        self._adapters[descriptor.source_id] = adapter

    def get(self, source_id: str) -> MarketDataAdapter:
        return self._adapters[source_id]

    def source_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))


def collect_listings(
    registry: SourceRegistry,
    query: str,
    market_code: str,
    limit_per_source: int = 100,
    source_ids: tuple[str, ...] | None = None,
) -> IngestionReport:
    """Collect from approved adapters while preserving partial-failure visibility."""

    if not query.strip():
        raise ValueError("query cannot be empty")
    if not _MARKET_CODE.fullmatch(market_code):
        raise ValueError("market_code must be an uppercase two-letter code")
    if not 1 <= limit_per_source <= 1000:
        raise ValueError("limit_per_source must be between 1 and 1000")

    selected = registry.source_ids() if source_ids is None else tuple(sorted(set(source_ids)))
    observations: list[ListingObservation] = []
    failures: list[SourceFailure] = []
    seen_records: set[tuple[str, str]] = set()
    duplicate_count = 0

    for source_id in selected:
        try:
            adapter = registry.get(source_id)
            if adapter.descriptor.permission_status != "approved":
                raise SourcePermissionError("source permission is no longer approved")
            returned = adapter.fetch_listings(query, market_code, limit_per_source)
            count = 0
            for item in returned:
                if count >= limit_per_source:
                    raise ValueError("adapter exceeded the requested result limit")
                if not isinstance(item, ListingObservation):
                    raise TypeError("adapter returned a non-ListingObservation value")
                if item.source_id != source_id:
                    raise ValueError("observation source_id does not match the registered adapter")
                if item.market_code != market_code:
                    raise ValueError("observation market_code does not match the requested market")
                count += 1
                record_key = (item.source_id, item.source_record_id)
                if record_key in seen_records:
                    duplicate_count += 1
                    continue
                seen_records.add(record_key)
                observations.append(item)
        except Exception as exc:
            failures.append(
                SourceFailure(
                    source_id=source_id,
                    error_type=type(exc).__name__,
                    message=str(exc)[:500],
                )
            )

    observations.sort(key=lambda item: (item.source_id, item.source_record_id))
    return IngestionReport(
        requested_sources=selected,
        observations=tuple(observations),
        failures=tuple(failures),
        duplicate_source_records=duplicate_count,
    )


def normalize_text(value: str | None) -> str:
    """Normalize text for exact matching only; this is not fuzzy entity resolution."""

    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    return " ".join("".join(char if char.isalnum() else " " for char in normalized).split())


def is_valid_gtin(value: str | None) -> bool:
    if value is None:
        return False
    digits = value.strip()
    if len(digits) not in _GTIN_LENGTHS or not digits.isdigit():
        return False
    payload = digits[:-1]
    weighted_sum = sum(
        int(digit) * (3 if (len(payload) - index) % 2 == 1 else 1)
        for index, digit in enumerate(payload)
    )
    expected_check_digit = (10 - weighted_sum % 10) % 10
    return expected_check_digit == int(digits[-1])


def product_identity_key(item: ListingObservation) -> str:
    """Use strong identifiers first; otherwise avoid cross-source fuzzy merging."""

    if is_valid_gtin(item.gtin):
        return f"gtin:{item.gtin.strip().zfill(14)}"

    brand = normalize_text(item.brand)
    mpn = normalize_text(item.manufacturer_part_number)
    if brand and mpn:
        return f"mpn:{brand}|{mpn}"

    title = normalize_text(item.title)
    variant = normalize_text(item.variant)
    if brand and title and variant:
        return f"exact-title:{brand}|{title}|{variant}"

    return f"source-record:{item.source_id}|{item.source_record_id}"


def group_product_listings(
    observations: Iterable[ListingObservation],
) -> tuple[ProductCluster, ...]:
    """Group only on validated GTIN, exact brand+MPN, or exact brand+title+variant."""

    groups: dict[str, list[ListingObservation]] = {}
    for item in observations:
        key = product_identity_key(item)
        groups.setdefault(key, []).append(item)

    clusters = [
        ProductCluster(
            identity_key=key,
            listings=tuple(sorted(items, key=lambda row: (row.source_id, row.source_record_id))),
        )
        for key, items in groups.items()
    ]
    return tuple(sorted(clusters, key=lambda cluster: cluster.identity_key))
