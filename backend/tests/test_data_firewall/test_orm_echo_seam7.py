"""DB-free tests for ORM-echo seam 7 (#36-37 gate-only denorm persist)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.data_firewall.firewall import FirewallOutcome
from app.modules.data_firewall.signing import SignedRecord, reset_signing_settings_cache
from app.modules.data_firewall.update_validator import SCRAPE_UPDATE_ALLOWLIST
from app.modules.ingestion.service import IngestionService
from app.modules.persist.scrape_gate_fields import (
    build_listing_update_fields,
    build_product_update_fields,
)
from app.modules.persist.writer import PersistContext, PersistResult

BACKEND_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _data_firewall_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_FIREWALL_SIGNING_SECRET", "unit-test-data-firewall-secret")
    reset_signing_settings_cache()
    yield
    reset_signing_settings_cache()


def test_no_orm_cache_sync_helpers_remain() -> None:
    ingestion = (BACKEND_ROOT / "app/modules/ingestion/service.py").read_text(
        encoding="utf-8",
    )
    scrape_fields = (
        BACKEND_ROOT / "app/modules/persist/scrape_gate_fields.py"
    ).read_text(encoding="utf-8")
    scraper = (BACKEND_ROOT / "app/modules/scraper/service.py").read_text(
        encoding="utf-8",
    )
    assert "_sync_product_enrich_cache" not in ingestion
    assert "_sync_listing_denorm_cache" not in ingestion
    assert "sync_listing_gate_cache" not in scrape_fields
    assert "sync_listing_gate_cache" not in scraper


def test_denorm_columns_in_gated_allowlists() -> None:
    assert SCRAPE_UPDATE_ALLOWLIST["dim_product"]["product_enrich"] == frozenset(
        {"name", "name_normalized", "image_url"},
    )
    assert SCRAPE_UPDATE_ALLOWLIST["fact_listing"]["listing_denorm_success"] == frozenset(
        {"last_price", "last_currency_code", "last_price_changed_at", "last_price_eur"},
    )
    assert SCRAPE_UPDATE_ALLOWLIST["fact_listing"]["listing_denorm_no_change"] == frozenset(
        {"last_checked_at", "last_price", "last_currency_code", "last_price_eur"},
    )


def test_build_fields_cover_all_denorm_columns() -> None:
    now = datetime.now(tz=timezone.utc)
    enrich = build_product_update_fields(
        product_id=uuid4(),
        name="Title",
        name_normalized="title",
        image_url="https://example.com/i.jpg",
    )
    assert set(enrich.keys()) - {"id"} == {
        "name",
        "name_normalized",
        "image_url",
    }

    success = build_listing_update_fields(
        url_hash="hash",
        last_price=Decimal("12.50"),
        last_currency_code="EUR",
        last_price_changed_at=now,
        last_price_eur=Decimal("12.50"),
    )
    assert set(success.keys()) - {"url_hash"} == {
        "last_price",
        "last_currency_code",
        "last_price_changed_at",
        "last_price_eur",
    }


def test_ingestion_persist_extracted_leaves_listing_denorm_unmutated_in_memory() -> None:
    """Gate Core UPDATE persists denorm; no post-gate setattr ORM echo."""
    db = MagicMock()
    product = type("Product", (), {"name": "old", "name_normalized": "old", "image_url": None})()
    db.get.return_value = product

    class _Listing:
        id = uuid4()
        product_id = uuid4()
        marketplace_id = uuid4()
        external_url = "https://shop.example/p/1"
        url_hash = "urlhash"
        last_price = None
        last_currency_code = None
        last_price_eur = None

    listing = _Listing()

    data = MagicMock()
    data.product_name = "Widget"
    data.title = "Widget"
    data.price = 19.99
    data.currency = "EUR"
    data.currency_raw = "EUR"
    data.original_price = None
    data.image_url = None
    data.page_role = "product"

    signed_price = SignedRecord(
        table="fact_price",
        operation="insert",
        locator={"listing_id": str(listing.id), "date_id": 20990101},
        fields={
            "listing_id": str(listing.id),
            "date_id": 20990101,
            "price": 19.99,
            "currency_code": "EUR",
            "scraped_at": datetime.now(tz=timezone.utc).isoformat(),
        },
        signature="sig",
    )

    with (
        patch(
            "app.modules.ingestion.service._today_date_id",
            return_value=20990101,
        ),
        patch(
            "app.modules.ingestion.service.evaluate_ecommerce",
            return_value=FirewallOutcome(
                passed=True,
                reject_reason=None,
                failed_rules=[],
                forced_log_status=None,
                page_role_verdict=None,
                signed_record=signed_price,
            ),
        ),
        patch(
            "app.modules.ingestion.service.authorize_scrape_update",
        ) as mock_auth,
        patch(
            "app.modules.ingestion.service.write_sync",
            return_value=PersistResult(ok=True, rows_affected=1),
        ),
    ):
        mock_auth.return_value = FirewallOutcome(
            passed=True,
            reject_reason=None,
            failed_rules=[],
            forced_log_status=None,
            page_role_verdict=None,
            signed_record=SignedRecord(
                table="fact_listing",
                operation="update",
                locator={"url_hash": "urlhash"},
                fields={"url_hash": "urlhash"},
                signature="sig2",
            ),
        )
        svc = IngestionService(db)
        svc._currency_resolver = MagicMock()
        svc.persist_extracted(data=data, listing=listing)  # type: ignore[arg-type]

    db.commit.assert_called_once()
    assert listing.last_price is None
    assert listing.last_price_eur is None


def test_scraper_housekeeping_commit_without_cache_sync() -> None:
    from app.modules.scraper.service import GlobalScrapeService

    db = MagicMock()
    listing = MagicMock()
    listing.id = uuid4()
    listing.external_url = "https://shop.example/p/1"

    svc = GlobalScrapeService(db, MagicMock())
    result = svc._persist_listing_housekeeping_or_fail(
        listing,
        url=listing.external_url,
        data=None,
    )

    assert result is None
    db.flush.assert_called_once()
    db.commit.assert_called_once()
