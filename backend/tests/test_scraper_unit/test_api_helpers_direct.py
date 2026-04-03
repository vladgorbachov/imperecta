"""Direct calls to api.py helpers (covers serialization without Celery/HTTP)."""

from __future__ import annotations

from app.modules.scraper import api as scraper_api
from app.modules.scraper.extractors import ExtractedProduct
from app.modules.scraper.scraper_pool import PoolScrapeResult


def test_pool_scrape_result_example_shape():
    d = scraper_api._pool_scrape_result_example()
    assert d["success"] is True
    assert d["data"]["title"] == "Sample product"


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
