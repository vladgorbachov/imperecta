"""Celery task helpers: technical_error log persistence."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.models.app_tables import ScrapeLog
from app.models.facts import FactListing
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

    def fake_factory():
        factory_calls.append(1)
        return session

    monkeypatch.setattr("app.modules.scraper.tasks.sync_session_factory", fake_factory)
    _persist_technical_error_log(listing_id, "Traceback\nline1\n")
    session.add.assert_called_once()
    arg = session.add.call_args[0][0]
    assert isinstance(arg, ScrapeLog)
    assert arg.status == "technical_error"
    assert "line1" in (arg.error_message or "")
    session.commit.assert_called_once()
    session.close.assert_called_once()
