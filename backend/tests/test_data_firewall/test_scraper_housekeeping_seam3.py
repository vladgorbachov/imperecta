"""Pure-logic tests for scrape housekeeping gate routing (seam 3)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.sql.dml import Update

from app.modules.data_firewall.signing import reset_signing_settings_cache
from app.modules.data_firewall.update_validator import (
    REJECT_REACTIVATION_FORBIDDEN,
    authorize_scrape_update,
)
from app.modules.persist.scrape_gate_fields import build_listing_update_fields
from app.modules.persist.writer import PersistContext, write_sync
from app.modules.scraper.scraper_pool import PoolScrapeResult
from app.modules.scraper.service import (
    GlobalScrapeService,
    LISTING_DEACTIVATE_AFTER_ERRORS,
)


@pytest.fixture(autouse=True)
def _data_firewall_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_FIREWALL_SIGNING_SECRET", "unit-test-data-firewall-secret")
    reset_signing_settings_cache()
    yield
    reset_signing_settings_cache()


def _capture_execute(db: MagicMock, *, rowcount: int = 1) -> list:
    captured: list = []

    def _execute(stmt):
        captured.append(stmt)
        result = MagicMock()
        result.rowcount = rowcount
        return result

    db.execute.side_effect = _execute
    return captured


@pytest.mark.parametrize(
    ("kind", "delta"),
    [
        (
            "listing_scrape_start_reset",
            {"consecutive_errors": 0, "last_error": None},
        ),
        ("listing_success_streak_reset", {"failure_streak": 0}),
        ("listing_checked", {"last_checked_at": datetime.now(tz=timezone.utc)}),
        (
            "listing_housekeeping_failure",
            {
                "consecutive_errors": 2,
                "last_error": "fetch_failed",
                "failure_streak": 3,
            },
        ),
        ("listing_deactivate", {"is_active": False}),
    ],
)
def test_each_housekeeping_kind_routes_by_url_hash(kind: str, delta: dict) -> None:
    fields = build_listing_update_fields(url_hash="listinghash", **delta)
    outcome = authorize_scrape_update(
        table="fact_listing",
        kind=kind,
        fields=fields,
        db=MagicMock(),
    )
    assert outcome.passed is True
    assert outcome.signed_record is not None
    assert outcome.signed_record.locator == {"url_hash": "listinghash"}
    assert outcome.signed_record.operation == "update"

    db = MagicMock()
    captured = _capture_execute(db)
    write_sync(db, outcome.signed_record, ctx=PersistContext(source="test"))
    assert isinstance(captured[0], Update)


def test_deactivate_rejects_is_active_true() -> None:
    fields = build_listing_update_fields(url_hash="listinghash", is_active=True)
    outcome = authorize_scrape_update(
        table="fact_listing",
        kind="listing_deactivate",
        fields=fields,
        db=MagicMock(),
    )
    assert outcome.passed is False
    assert outcome.reject_reason == REJECT_REACTIVATION_FORBIDDEN


def test_failure_at_threshold_issues_two_signed_updates() -> None:
    """Housekeeping counters and deactivate are separate kinds (no allowlist merge)."""
    db = MagicMock()
    listing = MagicMock()
    listing.url_hash = "hash"
    listing.marketplace_id = uuid4()
    listing.id = uuid4()
    listing.consecutive_errors = 0
    listing.failure_streak = LISTING_DEACTIVATE_AFTER_ERRORS - 1
    listing.external_url = "https://example.com/item"

    svc = GlobalScrapeService(db, MagicMock())
    with patch.object(svc, "_persist_listing_gate_update") as mock_gate:
        mock_gate.return_value = True
        svc._route_failure_housekeeping_updates(
            listing,
            listing_id=listing.id,
            result=PoolScrapeResult(
                success=False,
                url=listing.external_url,
                error="fetch_failed",
            ),
        )

    assert mock_gate.call_count == 2
    kinds = [call.kwargs["kind"] for call in mock_gate.call_args_list]
    assert kinds == ["listing_housekeeping_failure", "listing_deactivate"]
    hk_fields = mock_gate.call_args_list[0].kwargs["fields"]
    assert set(hk_fields.keys()) == {
        "url_hash",
        "consecutive_errors",
        "last_error",
        "failure_streak",
    }
    deactivate_fields = mock_gate.call_args_list[1].kwargs["fields"]
    assert deactivate_fields == {"url_hash": "hash", "is_active": False}


def _patch_scrape_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        GlobalScrapeService,
        "_listing_scrape_context",
        lambda self, listing: (False, 0, {}),
    )


def test_start_reset_syncs_in_memory_before_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.models.facts import FactListing

    listing_id = uuid4()
    listing = FactListing(
        id=listing_id,
        product_id=uuid4(),
        marketplace_id=uuid4(),
        external_url="https://example.com/item",
        url_hash=FactListing.compute_url_hash("https://example.com/item"),
    )
    listing.consecutive_errors = 9
    listing.last_error = "stale"

    session = MagicMock()
    session.get.return_value = listing
    session.execute = MagicMock(return_value=MagicMock(rowcount=1))

    seen: dict[str, int | None] = {}

    def capture_worker(coro):
        seen["ce"] = listing.consecutive_errors
        seen["le"] = listing.last_error
        import inspect

        if inspect.iscoroutine(coro):
            coro.close()
        return PoolScrapeResult(success=False, url=listing.external_url, error="err")

    monkeypatch.setattr("app.modules.scraper.service._run_coro_in_worker", capture_worker)
    _patch_scrape_context(monkeypatch)
    with patch(
        "app.modules.scraper.service.persist_logs_batch",
        return_value=MagicMock(ok=True),
    ):
        svc = GlobalScrapeService(session, MagicMock())
        svc.scrape_product(listing_id)
    assert seen["ce"] == 0
    assert seen["le"] is None


def test_failure_path_uses_housekeeping_commit_not_ingestion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.models.facts import FactListing

    listing_id = uuid4()
    listing = FactListing(
        id=listing_id,
        product_id=uuid4(),
        marketplace_id=uuid4(),
        external_url="https://example.com/item",
        url_hash=FactListing.compute_url_hash("https://example.com/item"),
    )
    session = MagicMock()
    session.get.return_value = listing
    session.execute = MagicMock(return_value=MagicMock(rowcount=1))

    def failing_worker(coro):
        import inspect

        if inspect.iscoroutine(coro):
            coro.close()
        return PoolScrapeResult(success=False, url=listing.external_url, error="err")

    monkeypatch.setattr("app.modules.scraper.service._run_coro_in_worker", failing_worker)
    _patch_scrape_context(monkeypatch)
    with (
        patch(
            "app.modules.scraper.service.IngestionService",
        ) as mock_ingestion,
        patch(
            "app.modules.scraper.service.persist_logs_batch",
            return_value=MagicMock(ok=True),
        ),
    ):
        svc = GlobalScrapeService(session, MagicMock())
        svc.scrape_product(listing_id)
    mock_ingestion.assert_not_called()
    session.commit.assert_called()


def test_success_path_start_reset_rides_ingestion_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.models.facts import FactListing
    from app.modules.ingestion.dto import IngestionResult

    listing_id = uuid4()
    listing = FactListing(
        id=listing_id,
        product_id=uuid4(),
        marketplace_id=uuid4(),
        external_url="https://example.com/item",
        url_hash=FactListing.compute_url_hash("https://example.com/item"),
    )
    session = MagicMock()
    session.get.return_value = listing
    session.execute = MagicMock(return_value=MagicMock(rowcount=1))

    def ok_worker(coro):
        import inspect

        if inspect.iscoroutine(coro):
            coro.close()
        return PoolScrapeResult(
            success=True,
            url=listing.external_url,
            data=MagicMock(
                product_name="T",
                title="T",
                price=1.0,
                currency="USD",
                currency_raw="USD",
                original_price=None,
                page_role="product",
            ),
        )

    monkeypatch.setattr("app.modules.scraper.service._run_coro_in_worker", ok_worker)
    _patch_scrape_context(monkeypatch)
    housekeeping_commits: list[int] = []
    original_hk = GlobalScrapeService._persist_listing_housekeeping_or_fail

    def track_hk(self, *args, **kwargs):
        housekeeping_commits.append(1)
        return original_hk(self, *args, **kwargs)

    with (
        patch.object(GlobalScrapeService, "_persist_listing_housekeeping_or_fail", track_hk),
        patch(
            "app.modules.scraper.service.IngestionService",
        ) as mock_ing_cls,
        patch(
            "app.modules.scraper.service.persist_logs_batch",
            return_value=MagicMock(ok=True),
        ),
    ):
        mock_ing_cls.return_value.persist_extracted.return_value = IngestionResult(
            persisted=True,
            log_status="success",
            skip_reason=None,
            price_found=1.0,
            persist_failed=False,
        )
        svc = GlobalScrapeService(session, MagicMock())
        svc.scrape_product(listing_id)

    assert housekeeping_commits == []
    mock_ing_cls.return_value.persist_extracted.assert_called_once()
