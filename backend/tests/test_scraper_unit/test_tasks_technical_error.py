"""Celery task helpers: technical_error log persistence."""

from unittest.mock import MagicMock
from uuid import uuid4

from app.models.facts import FactListing
from app.modules.persist.writer import PersistResult
from app.modules.scraper.tasks import _persist_technical_error_log


def test_persist_technical_error_log_writes_row(monkeypatch):
    listing_id = uuid4()
    product_id = uuid4()
    mp_id = uuid4()
    listing = FactListing(
        id=listing_id,
        product_id=product_id,
        marketplace_id=mp_id,
        external_url="https://example.com/x",
        url_hash="abc",
    )
    session = MagicMock()
    session.get.return_value = listing
    factory_calls: list = []
    write_calls: list = []

    def fake_factory():
        factory_calls.append(1)
        return session

    def fake_write_logs_sync(*, table, rows, reject_source):
        write_calls.append({"table": table, "rows": rows, "reject_source": reject_source})
        return PersistResult(ok=True, rows_affected=1)

    monkeypatch.setattr("app.modules.scraper.tasks.sync_session_factory", fake_factory)
    monkeypatch.setattr("app.modules.scraper.tasks.write_logs_sync", fake_write_logs_sync)
    _persist_technical_error_log(listing_id, "Traceback\nline1\n")
    assert len(factory_calls) == 1
    assert len(write_calls) == 1
    assert write_calls[0]["table"] == "scrape_logs"
    assert write_calls[0]["reject_source"] == "scraper_technical_error"
    row = write_calls[0]["rows"][0]
    assert row["status"] == "technical_error"
    assert "line1" in (row.get("error_message") or "")
    session.add.assert_not_called()
    session.commit.assert_not_called()
    session.close.assert_called_once()
