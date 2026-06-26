"""Pure-logic tests for prune DELETE commit boundary fix."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.data_firewall.firewall import FirewallOutcome
from app.modules.data_firewall.signing import SignedRecord, reset_signing_settings_cache
from app.modules.persist.writer import PersistContext, PersistResult
from app.modules.scraper.scraper_pool import PoolScrapeResult
from app.modules.scraper.service import GlobalScrapeService


@pytest.fixture(autouse=True)
def _data_firewall_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_FIREWALL_SIGNING_SECRET", "unit-test-data-firewall-secret")
    reset_signing_settings_cache()
    yield
    reset_signing_settings_cache()


def _listing_stub() -> MagicMock:
    listing = MagicMock()
    listing.id = uuid4()
    listing.product_id = uuid4()
    listing.marketplace_id = uuid4()
    listing.external_url = "https://shop.example/hub"
    listing.url_hash = "listinghash"
    return listing


def test_prune_commits_after_gate_deletes_before_early_return() -> None:
    db = MagicMock()
    listing = _listing_stub()
    svc = GlobalScrapeService(db, MagicMock())
    svc._persist_scrape_log = MagicMock(return_value=True)

    with (
        patch(
            "app.modules.scraper.service.authorize_scrape_delete",
        ) as mock_auth,
        patch(
            "app.modules.scraper.service.write_sync",
            return_value=PersistResult(ok=True, rows_affected=1),
        ) as mock_write,
    ):
        mock_auth.side_effect = [
            FirewallOutcome(
                passed=True,
                reject_reason=None,
                failed_rules=[],
                forced_log_status=None,
                page_role_verdict=None,
                signed_record=SignedRecord(
                    table="fact_listing",
                    operation="delete",
                    locator={"url_hash": listing.url_hash},
                    fields={"url_hash": listing.url_hash},
                    signature="sig-listing",
                ),
            ),
            FirewallOutcome(
                passed=True,
                reject_reason=None,
                failed_rules=[],
                forced_log_status=None,
                page_role_verdict=None,
                signed_record=SignedRecord(
                    table="dim_product",
                    operation="delete",
                    locator={"id": str(listing.product_id)},
                    fields={"id": str(listing.product_id)},
                    signature="sig-product",
                ),
            ),
        ]
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        db.execute.return_value = count_result

        result = PoolScrapeResult(
            success=False,
            url=listing.external_url,
            error="parse",
            page_role="hub",
        )
        out = svc._persist_scrape_pool_result(
            listing.id,
            listing,
            result,
            now=MagicMock(),
        )

    assert out.log_status == "not_a_product"
    assert mock_write.call_count == 2
    db.commit.assert_called_once()
    svc._persist_scrape_log.assert_called_once()


def test_prune_pair_atomicity_orphan_gates_product_delete() -> None:
    db = MagicMock()
    listing = _listing_stub()
    svc = GlobalScrapeService(db, MagicMock())

    with (
        patch(
            "app.modules.scraper.service.authorize_scrape_delete",
        ) as mock_auth,
        patch(
            "app.modules.scraper.service.write_sync",
            return_value=PersistResult(ok=True, rows_affected=1),
        ) as mock_write,
    ):
        mock_auth.return_value = FirewallOutcome(
            passed=True,
            reject_reason=None,
            failed_rules=[],
            forced_log_status=None,
            page_role_verdict=None,
            signed_record=SignedRecord(
                table="fact_listing",
                operation="delete",
                locator={"url_hash": listing.url_hash},
                fields={"url_hash": listing.url_hash},
                signature="sig-listing",
            ),
        )
        count_result = MagicMock()
        count_result.scalar.return_value = 2
        db.execute.return_value = count_result

        ok = svc._prune_confirmed_nonproduct(listing, page_role="hub")

    assert ok is True
    assert mock_auth.call_count == 1
    assert mock_write.call_count == 1
    db.commit.assert_called_once()


def test_prune_reject_does_not_commit() -> None:
    db = MagicMock()
    listing = _listing_stub()
    svc = GlobalScrapeService(db, MagicMock())

    with patch(
        "app.modules.scraper.service.authorize_scrape_delete",
        return_value=FirewallOutcome(
            passed=False,
            reject_reason="missing_locator",
            failed_rules=["missing_locator"],
            forced_log_status=None,
            page_role_verdict=None,
            signed_record=None,
        ),
    ), patch("app.modules.scraper.service.write_sync") as mock_write:
        ok = svc._prune_confirmed_nonproduct(listing, page_role="hub")

    assert ok is False
    mock_write.assert_not_called()
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_prune_write_sync_failure_rolls_back_pair() -> None:
    db = MagicMock()
    listing = _listing_stub()
    svc = GlobalScrapeService(db, MagicMock())

    with (
        patch(
            "app.modules.scraper.service.authorize_scrape_delete",
            return_value=FirewallOutcome(
                passed=True,
                reject_reason=None,
                failed_rules=[],
                forced_log_status=None,
                page_role_verdict=None,
                signed_record=SignedRecord(
                    table="fact_listing",
                    operation="delete",
                    locator={"url_hash": listing.url_hash},
                    fields={"url_hash": listing.url_hash},
                    signature="sig-listing",
                ),
            ),
        ),
        patch(
            "app.modules.scraper.service.write_sync",
            return_value=PersistResult(ok=False),
        ),
    ):
        ok = svc._prune_confirmed_nonproduct(listing, page_role="hub")

    assert ok is False
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_prune_uses_same_sync_session_no_bridge() -> None:
    db = MagicMock()
    listing = _listing_stub()
    svc = GlobalScrapeService(db, MagicMock())

    with (
        patch(
            "app.modules.scraper.service.authorize_scrape_delete",
        ) as mock_auth,
        patch(
            "app.modules.scraper.service.write_sync",
            return_value=PersistResult(ok=True, rows_affected=1),
        ) as mock_write,
    ):
        mock_auth.side_effect = [
            FirewallOutcome(
                passed=True,
                reject_reason=None,
                failed_rules=[],
                forced_log_status=None,
                page_role_verdict=None,
                signed_record=SignedRecord(
                    table="fact_listing",
                    operation="delete",
                    locator={"url_hash": listing.url_hash},
                    fields={"url_hash": listing.url_hash},
                    signature="sig-listing",
                ),
            ),
            FirewallOutcome(
                passed=True,
                reject_reason=None,
                failed_rules=[],
                forced_log_status=None,
                page_role_verdict=None,
                signed_record=SignedRecord(
                    table="dim_product",
                    operation="delete",
                    locator={"id": str(listing.product_id)},
                    fields={"id": str(listing.product_id)},
                    signature="sig-product",
                ),
            ),
        ]
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        db.execute.return_value = count_result

        ok = svc._prune_confirmed_nonproduct(listing, page_role="hub")

    assert ok is True
    assert svc.db is db
    assert mock_write.call_args_list[0].args[0] is db
    assert mock_write.call_args_list[1].args[0] is db
    db.commit.assert_called_once()
