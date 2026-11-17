from datetime import datetime, timezone
from decimal import Decimal

import pytest

from mega_market.catalog import (
    ListingObservation,
    SourceDescriptor,
    SourcePermissionError,
    SourceRegistry,
    collect_listings,
    group_product_listings,
    is_valid_gtin,
    product_identity_key,
)
from mega_market.economics import Money


NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


def descriptor(source_id: str = "catalog-a", permission_status: str = "approved") -> SourceDescriptor:
    return SourceDescriptor(
        source_id=source_id,
        display_name=source_id,
        access_mode="public_api",
        permission_status=permission_status,  # type: ignore[arg-type]
        permission_reference="terms://reviewed-source" if permission_status == "approved" else None,
        terms_reviewed_at=NOW if permission_status == "approved" else None,
    )


def listing(
    source_id: str = "catalog-a",
    record_id: str = "item-1",
    *,
    title: str = "Widget Pro 128 GB",
    brand: str | None = "Acme",
    mpn: str | None = "AP-128",
    gtin: str | None = None,
    variant: str | None = "128 GB / Black",
    market_code: str = "DE",
) -> ListingObservation:
    return ListingObservation(
        source_id=source_id,
        source_record_id=record_id,
        observed_at=NOW,
        title=title,
        price=Money(Decimal("49.90"), "EUR"),
        market_code=market_code,
        brand=brand,
        manufacturer_part_number=mpn,
        gtin=gtin,
        variant=variant,
        availability="in_stock",
    )


class FakeAdapter:
    def __init__(self, source: SourceDescriptor, rows: tuple[ListingObservation, ...]) -> None:
        self._descriptor = source
        self.rows = rows
        self.calls: list[tuple[str, str, int]] = []

    @property
    def descriptor(self) -> SourceDescriptor:
        return self._descriptor

    def fetch_listings(self, query: str, market_code: str, limit: int):
        self.calls.append((query, market_code, limit))
        return self.rows


def test_registry_rejects_pending_sources() -> None:
    registry = SourceRegistry()
    with pytest.raises(SourcePermissionError):
        registry.register(FakeAdapter(descriptor(permission_status="pending"), ()))


def test_registry_rejects_duplicate_source_ids() -> None:
    registry = SourceRegistry()
    registry.register(FakeAdapter(descriptor(), ()))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(FakeAdapter(descriptor(), ()))


def test_collect_passes_query_market_and_limit_to_adapter() -> None:
    adapter = FakeAdapter(descriptor(), (listing(),))
    registry = SourceRegistry()
    registry.register(adapter)

    report = collect_listings(registry, "wireless keyboard", "DE", limit_per_source=20)

    assert adapter.calls == [("wireless keyboard", "DE", 20)]
    assert report.complete is True
    assert len(report.observations) == 1


def test_collect_rejects_source_identity_spoofing() -> None:
    adapter = FakeAdapter(descriptor(), (listing(source_id="other-source"),))
    registry = SourceRegistry()
    registry.register(adapter)

    report = collect_listings(registry, "keyboard", "DE")

    assert report.observations == ()
    assert report.failures[0].error_type == "ValueError"


def test_collect_rejects_wrong_market() -> None:
    adapter = FakeAdapter(descriptor(), (listing(market_code="FR"),))
    registry = SourceRegistry()
    registry.register(adapter)

    report = collect_listings(registry, "keyboard", "DE")

    assert report.observations == ()
    assert "market_code" in report.failures[0].message


def test_collect_deduplicates_repeated_source_records() -> None:
    row = listing()
    adapter = FakeAdapter(descriptor(), (row, row))
    registry = SourceRegistry()
    registry.register(adapter)

    report = collect_listings(registry, "keyboard", "DE")

    assert len(report.observations) == 1
    assert report.duplicate_source_records == 1


def test_collect_keeps_other_sources_when_one_source_fails() -> None:
    class BrokenAdapter(FakeAdapter):
        def fetch_listings(self, query: str, market_code: str, limit: int):
            raise TimeoutError("source timeout")

    registry = SourceRegistry()
    registry.register(BrokenAdapter(descriptor("broken"), ()))
    registry.register(FakeAdapter(descriptor("healthy"), (listing("healthy"),)))

    report = collect_listings(registry, "keyboard", "DE")

    assert len(report.observations) == 1
    assert len(report.failures) == 1
    assert report.failures[0].source_id == "broken"
    assert report.complete is False


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("4006381333931", True),
        ("036000291452", True),
        ("96385074", True),
        ("4006381333932", False),
        ("not-a-gtin", False),
        (None, False),
    ],
)
def test_gtin_validation(value: str | None, expected: bool) -> None:
    assert is_valid_gtin(value) is expected


def test_gtin_normalizes_equivalent_ean_and_upc_to_same_width() -> None:
    ean = listing(gtin="4006381333931")
    assert product_identity_key(ean) == "gtin:04006381333931"


def test_exact_brand_and_mpn_match_across_sources() -> None:
    first = listing(source_id="a", record_id="1", gtin=None)
    second = listing(source_id="b", record_id="2", gtin=None, title="Different supplier title")
    assert product_identity_key(first) == product_identity_key(second)


def test_no_fuzzy_cross_source_merge_without_strong_identity() -> None:
    first = listing(source_id="a", record_id="1", brand=None, mpn=None, variant=None)
    second = listing(source_id="b", record_id="2", brand=None, mpn=None, variant=None)
    assert product_identity_key(first) != product_identity_key(second)


def test_exact_title_match_requires_brand_and_variant() -> None:
    first = listing(mpn=None, title="Wireless Keyboard", variant="US Layout")
    second = listing(source_id="b", record_id="2", mpn=None, title="Wireless Keyboard", variant="US Layout")
    assert product_identity_key(first) == product_identity_key(second)


def test_grouping_is_deterministic_and_preserves_all_observations() -> None:
    rows = (
        listing(source_id="b", record_id="2"),
        listing(source_id="a", record_id="1"),
        listing(source_id="c", record_id="3", brand=None, mpn=None, variant=None),
    )
    clusters = group_product_listings(rows)

    assert len(clusters) == 2
    assert sum(len(cluster.listings) for cluster in clusters) == 3
    assert clusters[0].listings[0].source_id == "a"


@pytest.mark.parametrize(
    ("query", "market_code", "limit"),
    [
        ("", "DE", 10),
        ("keyboard", "de", 10),
        ("keyboard", "DEU", 10),
        ("keyboard", "DE", 0),
        ("keyboard", "DE", 1001),
    ],
)
def test_collect_rejects_invalid_request(query: str, market_code: str, limit: int) -> None:
    with pytest.raises(ValueError):
        collect_listings(SourceRegistry(), query, market_code, limit)
