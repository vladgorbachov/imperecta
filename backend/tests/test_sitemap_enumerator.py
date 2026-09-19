"""Sitemap-full onboarding (slice 1): filtering, dedupe, batching, shard order."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch
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


def _marketplace(base_url="https://shop.example", country_code=None):
    return SimpleNamespace(
        id=uuid4(),
        base_url=base_url,
        locale=None,
        country_code=country_code,
        marketplace_code="shop_example",
    )


NEUTRAL_SHARD = "https://shop.example/sitemap-main.xml"
PRODUCT_SHARD = "https://shop.example/sitemap-products.xml"


def _pool_returning(urls, shard=NEUTRAL_SHARD):
    """Pool stub whose walk_sitemaps streams one parsed document per shard,
    mirroring the (url, shard) tuples the old candidates API returned."""
    pool = SimpleNamespace()
    entries = [u if isinstance(u, tuple) else (u, shard) for u in urls]
    by_shard: dict[str, list[str]] = {}
    for url, sh in entries:
        by_shard.setdefault(sh, []).append(url)

    async def walk(
        base_url, *, explicit_sitemaps=None, max_subfiles=None, prefetch=3, subfile_selector=None
    ):
        shards = list(by_shard)
        if subfile_selector is not None:
            shards = list(subfile_selector(shards))
        for sh in shards:
            locs = by_shard[sh]
            yield sh, {
                "sitemaps": [],
                "urls": list(locs),
                "url_entries": [{"loc": u, "alternates": {}, "lastmod": None} for u in locs],
            }

    pool.walk_sitemaps = walk
    return pool


def _pool_failing(exc):
    pool = SimpleNamespace()

    async def walk(base_url, **_kw):
        raise exc
        yield  # pragma: no cover - makes this an async generator

    pool.walk_sitemaps = walk
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
            patch.object(sitemap_enumerator, "_existing_hashes_sync", return_value={}),
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
                sitemap_enumerator, "_existing_hashes_sync", return_value={known_hash: None}
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
            patch.object(sitemap_enumerator, "_existing_hashes_sync", return_value={}),
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
        pool = _pool_failing(TimeoutError("slow"))
        result = await sitemap_enumerator.enumerate_sitemap_full(_marketplace(), pool)
        assert result.status == "error:TimeoutError"


def test_admin_endpoint_registered():
    schema = app.openapi()
    entry = schema["paths"].get("/api/admin/parsing/sitemap-enumerate", {})
    assert "post" in entry


@pytest.mark.asyncio
class TestShardTrust:
    async def test_product_shard_urls_trusted_without_structural_match(self):
        """techmart-style one-segment slugs pass when listed in a product shard."""
        urls = [("https://shop.example/krushka-philips-ecoclassic", PRODUCT_SHARD)]
        with (
            patch.object(
                sitemap_enumerator,
                "write_pool_dtos_sync",
                lambda dtos: PoolWriteResult(inserted=len(dtos), rejected=0),
            ),
            patch.object(sitemap_enumerator, "_existing_hashes_sync", return_value={}),
        ):
            result = await sitemap_enumerator.enumerate_sitemap_full(
                _marketplace(), _pool_returning(urls)
            )
        assert result.inserted == 1

    async def test_neutral_shard_still_filters_but_accepts_slug_sku(self):
        urls = [
            ("https://shop.example/about-us", NEUTRAL_SHARD),          # rejected
            ("https://shop.example/baterii-cr2016-1b-5020082", NEUTRAL_SHARD),  # slug SKU
        ]
        with (
            patch.object(
                sitemap_enumerator,
                "write_pool_dtos_sync",
                lambda dtos: PoolWriteResult(inserted=len(dtos), rejected=0),
            ),
            patch.object(sitemap_enumerator, "_existing_hashes_sync", return_value={}),
        ):
            result = await sitemap_enumerator.enumerate_sitemap_full(
                _marketplace(), _pool_returning(urls)
            )
        assert result.inserted == 1
        assert result.product_like == 1


@pytest.mark.asyncio
async def test_walk_sitemaps_streams_documents_with_bounded_prefetch(monkeypatch):
    """Index -> two product shards; documents stream in dispatch order and
    nested shards are queued product-first."""
    from app.modules.scraper.scraper_pool import ScraperPool

    docs = {
        "https://s.example/sitemap.xml": (
            '<sitemapindex><sitemap><loc>https://s.example/sitemap-blog.xml</loc></sitemap>'
            "<sitemap><loc>https://s.example/sitemap-products.xml</loc></sitemap></sitemapindex>"
        ),
        "https://s.example/sitemap-products.xml": "<urlset><url><loc>https://s.example/p/1</loc></url></urlset>",
        "https://s.example/sitemap-blog.xml": "<urlset><url><loc>https://s.example/blog/x</loc></url></urlset>",
    }
    pool = ScraperPool()
    fetched: list[str] = []

    async def fake_doc(url, *, log_hint):
        fetched.append(url)
        return docs.get(url)

    async def fake_static(url, **_kw):
        return None  # no robots.txt

    monkeypatch.setattr(pool, "_fetch_sitemap_document", fake_doc)
    monkeypatch.setattr(pool, "_fetch_static", fake_static)
    out = []
    async for shard, parsed in pool.walk_sitemaps("https://s.example", prefetch=2):
        out.append((shard, parsed["urls"]))
    assert out[0][0] == "https://s.example/sitemap.xml" and out[0][1] == []
    # product shard is walked before the blog shard
    assert [s for s, _ in out[1:]] == [
        "https://s.example/sitemap-products.xml",
        "https://s.example/sitemap-blog.xml",
    ]
    assert out[1][1] == ["https://s.example/p/1"]


@pytest.mark.asyncio
class TestMultiLocaleTree:
    """pigu.lt shape: one product tree per storefront language plus image
    twins — the coordinator elects one locale on the index, shards treat it
    as authoritative, media files are never walked."""

    LT = "https://shop.example/lt/sitemap-products-1.xml"
    LT_IMG = "https://shop.example/lt/sitemap-products-images-1.xml"
    RU = "https://shop.example/ru/sitemap-products-1.xml"
    RU_IMG = "https://shop.example/ru/sitemap-products-images-1.xml"

    def _pool(self):
        return _pool_returning(
            [
                ("https://shop.example/lt/p/widget-123456", self.LT),
                ("https://shop.example/lt/p/gadget-234567", self.LT),
                ("https://shop.example/lt/p/widget-123456", self.LT_IMG),
                ("https://shop.example/ru/p/widget-123456", self.RU),
                ("https://shop.example/ru/p/gadget-234567", self.RU),
                ("https://shop.example/ru/p/widget-123456", self.RU_IMG),
            ]
        )

    async def test_elected_locale_wins_and_media_files_are_skipped(self):
        written = []

        def fake_write(dtos):
            written.extend(dtos)
            return PoolWriteResult(inserted=len(dtos), rejected=0)

        with (
            patch.object(sitemap_enumerator, "write_pool_dtos_sync", fake_write),
            patch.object(sitemap_enumerator, "_existing_hashes_sync", return_value={}),
        ):
            result = await sitemap_enumerator.enumerate_sitemap_full(
                _marketplace(country_code="LT"), self._pool(), locale="lt"
            )
        assert result.status == "completed"
        assert result.locale == "lt"
        assert result.subfiles_skipped_media == 2
        assert result.subfiles_skipped_locale == 1
        assert result.inserted == 2
        assert {dto.fact_listing["external_url"] for dto in written} == {
            "https://shop.example/lt/p/widget-123456",
            "https://shop.example/lt/p/gadget-234567",
        }

    async def test_whole_tree_walk_elects_from_pool_prefix(self):
        """A flat/whole-tree walk with no coordinator locale elects on the
        index: the pool's prefix breaks the tie when the index has it."""
        with (
            patch.object(sitemap_enumerator, "write_pool_dtos_sync",
                         lambda dtos: PoolWriteResult(inserted=len(dtos), rejected=0)),
            patch.object(sitemap_enumerator, "_existing_hashes_sync", return_value={}),
            patch("app.modules.discovery.sitemap_locale.canonical_locale_sync",
                  return_value="ru"),
        ):
            result = await sitemap_enumerator.enumerate_sitemap_full(
                _marketplace(country_code="LT"), self._pool(), whole_tree=True
            )
        assert result.locale == "ru"
        assert result.subfiles_skipped_locale == 1 and result.subfiles_skipped_media == 2
        assert result.inserted == 2

    async def test_ru_only_shard_is_skipped_whole_without_a_fetch(self):
        """A shard entirely under another locale than the coordinator's
        election never reaches the walker (the 11 ru shards of 2026-09-19
        were fetched and then dropped URL by URL — 114,405 of them)."""
        fetched: list[str] = []
        pool = SimpleNamespace()

        async def walk(base_url, *, explicit_sitemaps=None, subfile_selector=None, **_kw):
            files = list(explicit_sitemaps or [])
            if subfile_selector is not None:
                files = list(subfile_selector(files))
            for f in files:
                fetched.append(f)
                yield f, {"sitemaps": [], "urls": [], "url_entries": []}

        pool.walk_sitemaps = walk
        result = await sitemap_enumerator.enumerate_sitemap_full(
            _marketplace(country_code="LT"), pool, locale="lt",
            explicit_sitemaps=[self.RU, "https://shop.example/ru/sitemap-products-2.xml", self.RU_IMG],
        )
        assert fetched == []
        assert result.status == "empty_sitemap"
        assert result.locale == "lt"
        assert result.subfiles_skipped_locale == 2 and result.subfiles_skipped_media == 1

    async def test_shard_without_election_drops_nothing_and_never_consults_the_pool(self):
        """tsbohemia: files under /cs/, pool under /en/ (hreflang) — a shard
        with no coordinator locale walks its files whatever the pool says."""
        files = ["https://sitemap.shop.example/cs/sitemap-products-%d-cs.xml" % i for i in range(3)]
        urls = [(f"https://shop.example/en/p/item-{i:06d}", files[i]) for i in range(3)]
        with (
            patch.object(sitemap_enumerator, "write_pool_dtos_sync",
                         lambda dtos: PoolWriteResult(inserted=len(dtos), rejected=0)),
            patch.object(sitemap_enumerator, "_existing_hashes_sync", return_value={}),
            patch("app.modules.discovery.sitemap_locale.canonical_locale_sync",
                  side_effect=AssertionError("pool must not be consulted in a shard")),
        ):
            result = await sitemap_enumerator.enumerate_sitemap_full(
                _marketplace(country_code="CZ"), _pool_returning(urls), explicit_sitemaps=files
            )
        assert result.locale is None
        assert result.subfiles_skipped_locale == 0
        assert result.inserted == 3

    async def test_urls_are_never_filtered_by_locale(self):
        """hreflang selection may move a URL to another prefix; a product
        without an alternate keeps its own — both stay."""
        urls = [
            ("https://shop.example/lt/p/widget-123456", PRODUCT_SHARD),
            ("https://shop.example/ru/p/widget-123456", PRODUCT_SHARD),
            ("https://shop.example/p/plain-345678", PRODUCT_SHARD),
        ]
        with (
            patch.object(sitemap_enumerator, "write_pool_dtos_sync",
                         lambda dtos: PoolWriteResult(inserted=len(dtos), rejected=0)),
            patch.object(sitemap_enumerator, "_existing_hashes_sync", return_value={}),
        ):
            result = await sitemap_enumerator.enumerate_sitemap_full(
                _marketplace(), _pool_returning(urls), locale="lt"
            )
        assert result.inserted == 3

    async def test_run_floor_processes_the_paid_document_before_stopping(self):
        """max_urls is a floor for the run: the document that crossed it is
        written in full, the walk stops before the next one."""
        docs = {
            "https://shop.example/sitemap-products-1.xml": [f"https://shop.example/p/a-{i:06d}" for i in range(6)],
            "https://shop.example/sitemap-products-2.xml": [f"https://shop.example/p/b-{i:06d}" for i in range(6)],
            "https://shop.example/sitemap-products-3.xml": [f"https://shop.example/p/c-{i:06d}" for i in range(6)],
        }
        pool = SimpleNamespace()
        walked: list[str] = []

        async def walk(base_url, *, explicit_sitemaps=None, subfile_selector=None, **_kw):
            for f, locs in docs.items():
                walked.append(f)
                yield f, {"sitemaps": [], "urls": locs,
                          "url_entries": [{"loc": u, "alternates": {}, "lastmod": None} for u in locs]}

        pool.walk_sitemaps = walk
        with (
            patch.object(sitemap_enumerator, "write_pool_dtos_sync",
                         lambda dtos: PoolWriteResult(inserted=len(dtos), rejected=0)),
            patch.object(sitemap_enumerator, "_existing_hashes_sync", return_value={}),
        ):
            result = await sitemap_enumerator.enumerate_sitemap_full(
                _marketplace(), pool, max_urls=8
            )
        # doc1: 6 (<8, go on); doc2: raw 12 > 8 and 12 >= 8 -> processed, then stop
        assert result.inserted == 12
        assert walked == list(docs)[:2]
