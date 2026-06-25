"""Pure-logic tests for isolated reject_data durability (no DB/network)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.data_firewall.firewall import evaluate_market
from app.modules.data_firewall.reject_store import write_reject_data_isolated
from app.modules.data_firewall.signing import reset_signing_settings_cache
from app.modules.persist.writer import build_dim_product_fields, build_fact_listing_fields
from app.modules.scraper import discovery as disc


@pytest.fixture(autouse=True)
def _data_firewall_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_FIREWALL_SIGNING_SECRET", "unit-test-data-firewall-secret")
    reset_signing_settings_cache()
    yield
    reset_signing_settings_cache()


def test_reject_survives_business_savepoint_rollback() -> None:
    """Gate reject commits on audit session while business nested txn rolls back."""
    product_id = uuid4()
    marketplace_id = uuid4()
    listing_fields = build_fact_listing_fields(
        product_id=product_id,
        marketplace_id=marketplace_id,
        external_url="https://shop.example/p/1",
        url_hash="hash1",
    )
    listing_fields["url_hash"] = None
    dto = disc.PoolInsertDTO(
        marketplace_id=marketplace_id,
        dim_product=build_dim_product_fields(
            product_id=product_id,
            name="Item",
            name_normalized="item",
        ),
        fact_listing=listing_fields,
    )
    business_db = MagicMock()
    nested = MagicMock()
    business_db.begin_nested.return_value = nested
    audit_db = MagicMock()

    with patch("app.modules.scraper.discovery.sync_session_factory", return_value=business_db), patch(
        "app.database.sync_session_factory",
        return_value=audit_db,
    ), patch("app.modules.scraper.discovery.write_sync", return_value=True):
        result = disc._write_pool_dtos_sync([dto])

    assert result.inserted == 0
    assert result.rejected == 1
    nested.rollback.assert_called_once()
    audit_db.add.assert_called_once()
    audit_db.commit.assert_called_once()
    audit_db.close.assert_called_once()
    business_db.commit.assert_called_once()
    business_db.flush.assert_not_called()


def test_write_reject_data_isolated_swallows_failure() -> None:
    audit_db = MagicMock()
    audit_db.add.side_effect = RuntimeError("audit db down")

    with patch(
        "app.database.sync_session_factory",
        return_value=audit_db,
    ), patch("app.modules.data_firewall.reject_store.logger") as mock_logger:
        write_reject_data_isolated(
            source="discovery",
            table_target="fact_listing",
            reject_reason="contract_violation",
            raw_payload={"url_hash": None},
            rejected_by="data_firewall",
            operation="insert",
        )

    mock_logger.exception.assert_called_once()
    audit_db.close.assert_called_once()


def test_evaluate_market_reject_uses_isolated_session() -> None:
    """Non-savepoint callers still persist rejects via the isolated audit session."""
    audit_db = MagicMock()
    business_db = MagicMock()
    fields = {
        "date_id": 20250617,
        "currency_code": "EURO",
        "rate_to_eur": 1.0,
        "rate_to_usd": 1.1,
        "source": "test",
        "fetched_at": "2025-06-17T00:00:00+00:00",
    }

    with patch(
        "app.database.sync_session_factory",
        return_value=audit_db,
    ):
        outcome = evaluate_market(
            fields,
            table="fact_currency_rate",
            db=business_db,
            reject_source="market_forex",
        )

    assert outcome.passed is False
    audit_db.add.assert_called_once()
    audit_db.commit.assert_called_once()
    business_db.add.assert_not_called()
    business_db.flush.assert_not_called()
    business_db.commit.assert_not_called()
