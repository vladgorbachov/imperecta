"""Pure-logic tests for discovery pool write bridge (no DB/network)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.data_firewall.firewall import FirewallOutcome
from app.modules.data_firewall.signing import SignedRecord, reset_signing_settings_cache
from app.modules.persist.writer import (
    build_dim_product_fields,
    build_fact_listing_fields,
    build_fact_price_fields,
)
from app.modules.scraper import discovery as disc


@pytest.fixture(autouse=True)
def _data_firewall_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_FIREWALL_SIGNING_SECRET", "unit-test-data-firewall-secret")
    reset_signing_settings_cache()
    yield
    reset_signing_settings_cache()


def test_build_dim_product_fields_minimal() -> None:
    product_id = uuid4()
    fields = build_dim_product_fields(
        product_id=product_id,
        name="Widget",
        name_normalized="widget",
        is_active=True,
    )
    assert fields == {
        "id": product_id,
        "name": "Widget",
        "name_normalized": "widget",
        "is_active": True,
    }


def test_build_fact_listing_fields_minimal() -> None:
    product_id = uuid4()
    marketplace_id = uuid4()
    fields = build_fact_listing_fields(
        product_id=product_id,
        marketplace_id=marketplace_id,
        external_url="https://shop.example/p/1",
        url_hash="abc123",
        is_active=True,
        page_role="product",
    )
    assert fields["product_id"] == product_id
    assert fields["marketplace_id"] == marketplace_id
    assert fields["page_role"] == "product"


def test_build_fact_price_fields_unchanged_shape() -> None:
    listing_id = uuid4()
    from datetime import datetime, timezone

    fields = build_fact_price_fields(
        listing_id=listing_id,
        date_id=20250617,
        price=9.99,
        currency_code="EUR",
        original_price=None,
        discount_pct=None,
        price_change_pct=None,
        scraped_at=datetime(2025, 6, 17, tzinfo=timezone.utc),
        scrape_job_id=None,
    )
    assert fields["listing_id"] == listing_id
    assert fields["price"] == 9.99


def test_write_pool_dtos_sync_empty_batch() -> None:
    result = disc._write_pool_dtos_sync([])
    assert result.inserted == 0
    assert result.rejected == 0


def test_write_pool_dtos_sync_commits_successful_pair() -> None:
    product_id = uuid4()
    marketplace_id = uuid4()
    dto = disc.PoolInsertDTO(
        marketplace_id=marketplace_id,
        dim_product=build_dim_product_fields(
            product_id=product_id,
            name="Item",
            name_normalized="item",
        ),
        fact_listing=build_fact_listing_fields(
            product_id=product_id,
            marketplace_id=marketplace_id,
            external_url="https://shop.example/p/1",
            url_hash="hash1",
        ),
    )
    db = MagicMock()
    nested = MagicMock()
    db.begin_nested.return_value = nested

    with patch("app.modules.scraper.discovery.sync_session_factory", return_value=db), patch(
        "app.modules.scraper.discovery.evaluate_market",
        return_value=FirewallOutcome(
            passed=True,
            reject_reason=None,
            failed_rules=[],
            forced_log_status=None,
            page_role_verdict=None,
            signed_record=SignedRecord(table="x", fields={}, signature="sig"),
        ),
    ), patch("app.modules.scraper.discovery.write_sync", return_value=True):
        result = disc._write_pool_dtos_sync([dto])

    assert result.inserted == 1
    assert result.rejected == 0
    db.commit.assert_called_once()
    db.close.assert_called_once()
    assert nested.commit.call_count == 1


def test_write_pool_dtos_sync_rolls_back_batch_on_exception() -> None:
    product_id = uuid4()
    marketplace_id = uuid4()
    dto = disc.PoolInsertDTO(
        marketplace_id=marketplace_id,
        dim_product=build_dim_product_fields(
            product_id=product_id,
            name="Item",
            name_normalized="item",
        ),
        fact_listing=build_fact_listing_fields(
            product_id=product_id,
            marketplace_id=marketplace_id,
            external_url="https://shop.example/p/1",
            url_hash="hash1",
        ),
    )
    db = MagicMock()
    nested = MagicMock()
    db.begin_nested.return_value = nested

    with patch("app.modules.scraper.discovery.sync_session_factory", return_value=db), patch(
        "app.modules.scraper.discovery.evaluate_market",
        side_effect=RuntimeError("boom"),
    ):
        with pytest.raises(RuntimeError, match="boom"):
            disc._write_pool_dtos_sync([dto])

    db.rollback.assert_called_once()
    db.close.assert_called_once()
    nested.rollback.assert_called_once()


def test_write_pool_dtos_sync_rejects_pair_without_committing_orphan() -> None:
    product_id = uuid4()
    marketplace_id = uuid4()
    dto = disc.PoolInsertDTO(
        marketplace_id=marketplace_id,
        dim_product=build_dim_product_fields(
            product_id=product_id,
            name="Item",
            name_normalized="item",
        ),
        fact_listing=build_fact_listing_fields(
            product_id=product_id,
            marketplace_id=marketplace_id,
            external_url="https://shop.example/p/1",
            url_hash="hash1",
        ),
    )
    db = MagicMock()
    nested = MagicMock()
    db.begin_nested.return_value = nested
    product_ok = FirewallOutcome(
        passed=True,
        reject_reason=None,
        failed_rules=[],
        forced_log_status=None,
        page_role_verdict=None,
        signed_record=SignedRecord(table="dim_product", fields={}, signature="sig"),
    )
    listing_reject = FirewallOutcome(
        passed=False,
        reject_reason="contract",
        failed_rules=["name"],
        forced_log_status=None,
        page_role_verdict=None,
        signed_record=None,
    )

    with patch("app.modules.scraper.discovery.sync_session_factory", return_value=db), patch(
        "app.modules.scraper.discovery.evaluate_market",
        side_effect=[product_ok, listing_reject],
    ), patch("app.modules.scraper.discovery.write_sync", return_value=True):
        result = disc._write_pool_dtos_sync([dto])

    assert result.inserted == 0
    assert result.rejected == 1
    nested.rollback.assert_called_once()
    db.commit.assert_called_once()
