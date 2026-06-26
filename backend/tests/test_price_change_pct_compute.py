"""Pure-logic tests for fact_price.price_change_pct compute site (ingestion producer)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.ingestion.service import IngestionService
from app.modules.persist.writer import (
    MAX_ABS_PRICE_CHANGE_PCT,
    compute_price_change_pct,
)


def test_compute_prior_none_returns_none() -> None:
    assert compute_price_change_pct(new_price=100, prior_last_price=None) is None


def test_compute_prior_zero_returns_none() -> None:
    assert compute_price_change_pct(new_price=100, prior_last_price=0) is None


def test_compute_rise_100_to_120() -> None:
    result = compute_price_change_pct(new_price=120, prior_last_price=100)
    assert result == Decimal("20.0000")


def test_compute_fall_100_to_80() -> None:
    result = compute_price_change_pct(new_price=80, prior_last_price=100)
    assert result == Decimal("-20.0000")


def test_compute_extreme_clamped_to_cap() -> None:
    result = compute_price_change_pct(new_price=100_000, prior_last_price=1)
    assert result == MAX_ABS_PRICE_CHANGE_PCT


def test_compute_quantizes_to_scale_four() -> None:
    result = compute_price_change_pct(new_price=Decimal("10.3333"), prior_last_price=10)
    assert result == Decimal("3.3330")


def test_compute_decimal_no_float_drift() -> None:
    """Representative values stay exact under Decimal math."""
    result = compute_price_change_pct(
        new_price=Decimal("19.99"),
        prior_last_price=Decimal("17.50"),
    )
    expected = (
        (Decimal("19.99") - Decimal("17.50"))
        / Decimal("17.50")
        * Decimal("100")
    ).quantize(Decimal("0.0001"))
    assert result == expected
    assert isinstance(result, Decimal)


@pytest.fixture()
def patched_ingestion(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "app.modules.ingestion.service._today_date_id",
        lambda _db: 20990101,
    )
    from fixtures.scraper_fixtures import patch_resolve_price_eur_for_unit

    patch_resolve_price_eur_for_unit(monkeypatch)
    yield


def test_ingestion_passes_computed_price_change_pct(patched_ingestion) -> None:
    """Caller passes computed delta from listing.last_price before denorm."""
    db = MagicMock()
    db.get.return_value = SimpleNamespace(
        name="Sample",
        name_normalized="sample",
        image_url=None,
    )
    listing = SimpleNamespace(
        id=uuid4(),
        marketplace_id=uuid4(),
        product_id=uuid4(),
        external_url="https://example.com/p",
        url_hash="hash",
        last_price=100.0,
        last_currency_code="EUR",
        last_price_changed_at=None,
        last_checked_at=None,
    )
    svc = IngestionService(db)
    svc._currency_resolver = MagicMock()
    svc._currency_resolver.whitelist_for.return_value = frozenset({"EUR"})
    svc._currency_resolver.matches.return_value = True

    captured: dict = {}

    def capture_build(**kwargs):
        captured.update(kwargs)
        return {
            "listing_id": listing.id,
            "date_id": 20990101,
            "price": kwargs["price"],
            "currency_code": kwargs["currency_code"],
            "original_price": kwargs["original_price"],
            "discount_pct": kwargs["discount_pct"],
            "price_change_pct": kwargs["price_change_pct"],
            "scraped_at": kwargs["scraped_at"],
            "scrape_job_id": kwargs["scrape_job_id"],
            "price_eur": kwargs.get("price_eur"),
        }

    with (
        patch(
            "app.modules.ingestion.service.build_fact_price_fields",
            side_effect=capture_build,
        ),
        patch(
            "app.modules.ingestion.service.write_sync",
            return_value=MagicMock(ok=True, rows_affected=1),
        ),
    ):
        svc.persist_extracted(
            data=SimpleNamespace(
                product_name="Sample",
                title="Sample",
                price=120.0,
                currency="EUR",
                currency_raw="EUR",
                original_price=None,
                image_url=None,
                price_raw_text="120 EUR",
            ),
            listing=listing,
        )

    assert captured["price_change_pct"] == 20.0
    assert captured["discount_pct"] is None


def test_ingestion_first_scrape_price_change_pct_none(patched_ingestion) -> None:
    """No prior last_price -> honest None (first scrape)."""
    db = MagicMock()
    db.get.return_value = SimpleNamespace(
        name="Sample",
        name_normalized="sample",
        image_url=None,
    )
    listing = SimpleNamespace(
        id=uuid4(),
        marketplace_id=uuid4(),
        product_id=uuid4(),
        external_url="https://example.com/p",
        url_hash="hash",
        last_price=None,
        last_currency_code=None,
        last_price_changed_at=None,
        last_checked_at=None,
    )
    svc = IngestionService(db)
    svc._currency_resolver = MagicMock()
    svc._currency_resolver.whitelist_for.return_value = frozenset({"EUR"})
    svc._currency_resolver.matches.return_value = True

    captured: dict = {}

    def capture_build(**kwargs):
        captured.update(kwargs)
        return {
            "listing_id": listing.id,
            "date_id": 20990101,
            "price": kwargs["price"],
            "currency_code": kwargs["currency_code"],
            "original_price": None,
            "discount_pct": None,
            "price_change_pct": kwargs["price_change_pct"],
            "scraped_at": datetime.now(tz=timezone.utc),
            "scrape_job_id": None,
            "price_eur": None,
        }

    with (
        patch(
            "app.modules.ingestion.service.build_fact_price_fields",
            side_effect=capture_build,
        ),
        patch(
            "app.modules.ingestion.service.write_sync",
            return_value=MagicMock(ok=True, rows_affected=1),
        ),
    ):
        svc.persist_extracted(
            data=SimpleNamespace(
                product_name="Sample",
                title="Sample",
                price=99.99,
                currency="EUR",
                currency_raw="EUR",
                original_price=None,
                image_url=None,
                price_raw_text="99.99 EUR",
            ),
            listing=listing,
        )

    assert captured["price_change_pct"] is None
