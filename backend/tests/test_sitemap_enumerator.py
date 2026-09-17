"""Sitemap-full onboarding (slice 1): filtering, dedupe, batching, shard order."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.main import app
from app.modules.discovery import sitemap_enumerator
from app.modules.discovery.gate_persist import PoolWriteResult
from app.modules.scraper.scraper_pool import _sitemap_shard_priority


class TestShardPriority:
    def test_product_shards_first_chrome_last(self):
        shards = [
            "https://s.example/sitemap-blog.xml",
            "https://s.example/sitemap-products-1.xml",
            "https://s.example/sitemap-misc.xml",
            "https://s.example/sitemap-category.xml",
            "https://s.example/sitemap-tovar.xml",
        ]
        ordered = sorted(shards, key=_sitemap_shard_priority)
        assert ordered[0].endswith(("products-1.xml", "tovar.xml"))
        assert ordered[1].endswith(("products-1.xml", "tovar.xml"))
        assert ordered[2].endswith("misc.xml")
        assert set(ordered[3:]) == {
            "https://s.example/sitemap-blog.xml",
            "https://s.example/sitemap-category.xml",
        }


def _marketplace(base_url="https://shop.example"):
    return SimpleNamespace(
        id=uuid4(),
        base_url=base_url,
        locale=None,
        marketplace_code="shop_example",
    )


def _pool_returning(urls):
    pool = SimpleNamespace()
    pool.fetch_sitemap_candidates = AsyncMock(return_value=urls)
    return pool


@pytest.mark.asyncio
class TestEnumerate:
    async def test_filters_foreign_hosts_and_non_product_paths(self):
        urls = [
            "https://shop.example/p/widget-123456",     # product-like (digits)
            "https://shop.example/item/abc.html",       # product-like (.html)
            "https://shop.example/about",               # 1 segment, no hints
            "https://evil.example/p/widget-999999",     # foreign host
            "https://www.shop.example/p/gadget-777777", # www-variant of base host
        ]
        written = []

        def fake_write(dtos):
            written.extend(dtos)
            return PoolWriteResult(inserted=len(dtos), rejected=0)

        with (
            patch.object(sitemap_enumerator, "write_pool_dtos_sync", fake_write),
            patch.object(sitemap_enumerator, "_existing_hashes_sync", return_value=set()),
        ):
            result = await sitemap_enumerator.enumerate_sitemap_full(
                _marketplace(), _pool_returning(urls)
            )
        assert result.status == "completed"
        assert result.product_like == 3
        assert result.inserted == 3
        inserted_urls = {dto.fact_listing["external_url"] for dto in written}
        assert "https://evil.example/p/widget-999999" not in inserted_urls
        assert "https://shop.example/about" not in inserted_urls

    async def test_dedupes_against_pool_and_within_run(self):
        url = "https://shop.example/p/widget-123456"
        from app.models.facts import FactListing

        known_hash = FactListing.compute_url_hash(url)
        urls = [url, url, "https://shop.example/p/other-654321"]

        with (
            patch.object(
                sitemap_enumerator,
                "write_pool_dtos_sync",
                lambda dtos: PoolWriteResult(inserted=len(dtos), rejected=0),
            ),
            patch.object(
                sitemap_enumerator, "_existing_hashes_sync", return_value={known_hash}
            ),
        ):
            result = await sitemap_enumerator.enumerate_sitemap_full(
                _marketplace(), _pool_returning(urls)
            )
        assert result.inserted == 1  # only 'other'
        assert result.duplicates == 2  # pool-known + in-run repeat

    async def test_batches_at_batch_size(self):
        urls = [f"https://shop.example/p/item-{100000 + i}" for i in range(1100)]
        calls: list[int] = []

        def fake_write(dtos):
            calls.append(len(dtos))
            return PoolWriteResult(inserted=len(dtos), rejected=0)

        with (
            patch.object(sitemap_enumerator, "write_pool_dtos_sync", fake_write),
            patch.object(sitemap_enumerator, "_existing_hashes_sync", return_value=set()),
        ):
            result = await sitemap_enumerator.enumerate_sitemap_full(
                _marketplace(), _pool_returning(urls)
            )
        assert result.inserted == 1100
        assert calls == [500, 500, 100]

    async def test_empty_sitemap_is_honest(self):
        result = await sitemap_enumerator.enumerate_sitemap_full(
            _marketplace(), _pool_returning([])
        )
        assert result.status == "empty_sitemap"
        assert result.inserted == 0

    async def test_fetch_failure_reported_not_raised(self):
        pool = SimpleNamespace()
        pool.fetch_sitemap_candidates = AsyncMock(side_effect=TimeoutError("slow"))
        result = await sitemap_enumerator.enumerate_sitemap_full(_marketplace(), pool)
        assert result.status == "error:TimeoutError"


def test_admin_endpoint_registered():
    schema = app.openapi()
    entry = schema["paths"].get("/api/admin/parsing/sitemap-enumerate", {})
    assert "post" in entry
