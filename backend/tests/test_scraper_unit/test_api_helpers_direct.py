"""Direct calls to api.py helpers (serialization, TCP helper) without Celery/HTTP."""

from __future__ import annotations

from unittest.mock import patch

from app.modules.scraper import api as scraper_api
from app.modules.scraper.extractors import ExtractedProduct
from app.modules.scraper.scraper_pool import PoolScrapeResult


def test_decodo_tcp_reachable_false_on_bad_url():
    assert scraper_api._decodo_tcp_reachable("://") is False


def test_decodo_tcp_reachable_uses_socket():
    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    with patch("app.modules.scraper.api.socket.create_connection", return_value=_Conn()):
        assert scraper_api._decodo_tcp_reachable("https://example.com:443/") is True


def test_decodo_tcp_reachable_oserror():
    with patch(
        "app.modules.scraper.api.socket.create_connection",
        side_effect=OSError("unreachable"),
    ):
        assert scraper_api._decodo_tcp_reachable("https://example.com:443/") is False


def test_serialize_pool_result_with_and_without_data():
    r = PoolScrapeResult(
        success=True,
        url="https://u",
        data=ExtractedProduct(title="T", price=1.0, currency="USD"),
    )
    out = scraper_api._serialize_pool_result(r)
    assert out["data"]["title"] == "T"
    r2 = PoolScrapeResult(success=False, url="https://u", error="e")
    assert scraper_api._serialize_pool_result(r2)["data"] is None
