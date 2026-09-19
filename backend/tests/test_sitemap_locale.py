"""sitemap_locale: multi-locale / media sub-sitemap selection (both engines)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.discovery import sitemap_locale as sl

PIGU_INDEX = [
    "https://pigu.lt/lt/sitemap-products-1.xml",
    "https://pigu.lt/lt/sitemap-products-images-1.xml",
    "https://pigu.lt/ru/sitemap-products-1.xml",
    "https://pigu.lt/ru/sitemap-products-images-1.xml",
    "https://pigu.lt/ru/sitemap-filters-1.xml",
    "https://pigu.lt/sitemap-general.xml",
]


@pytest.fixture(params=["python", "rust"])
def engine(request, monkeypatch):
    if request.param == "rust":
        pytest.importorskip("imperecta_core")
    monkeypatch.setenv("EXTRACTOR_ENGINE", request.param)
    return request.param


class TestPrimitives:
    def test_locale_segment(self, engine):
        assert sl.url_locale_segment("https://pigu.lt/lt/p/1") == "lt"
        assert sl.url_locale_segment("https://pigu.lt/EN-us/p/1") == "en-us"
        assert sl.url_locale_segment("https://pigu.lt/p/1") is None
        assert sl.url_locale_segment("https://pigu.lt/tovar/1") is None
        assert sl.url_locale_segment("https://pigu.lt") is None

    def test_media_sitemap(self, engine):
        assert sl.is_media_sitemap("https://pigu.lt/lt/sitemap-products-images-3.xml")
        assert sl.is_media_sitemap("https://s.example/sitemap_video.xml")
        assert not sl.is_media_sitemap("https://pigu.lt/lt/sitemap-products-3.xml")
        assert not sl.is_media_sitemap("https://s.example/sitemap-news.xml")

    def test_selection_with_pool_locale(self, engine):
        sel = sl.select_sitemap_subfiles(PIGU_INDEX, "lt", "lt", fallback_to_first=True)
        assert sel.kept == ["https://pigu.lt/lt/sitemap-products-1.xml", "https://pigu.lt/sitemap-general.xml"]
        assert sel.skipped_media == 2 and sel.skipped_locale == 2 and sel.locale == "lt"

    def test_selection_country_hint_then_first(self, engine):
        assert sl.select_sitemap_subfiles(PIGU_INDEX, None, "ru").locale == "ru"
        assert sl.select_sitemap_subfiles(PIGU_INDEX, None, "et", fallback_to_first=True).locale == "lt"
        isolated = sl.select_sitemap_subfiles(PIGU_INDEX, None, None)
        assert isolated.locale is None and isolated.skipped_locale == 0
        assert len(isolated.kept) == 4

    def test_single_locale_tree_untouched(self, engine):
        files = ["https://s.example/lt/a.xml", "https://s.example/lt/b.xml", "https://s.example/c.xml"]
        sel = sl.select_sitemap_subfiles(files, "ru", "ru", fallback_to_first=True)
        assert sel.kept == files and sel.locale is None

    def test_dominant_locale_threshold(self, engine):
        pool = ["https://pigu.lt/lt/p/%d" % i for i in range(8)] + ["https://pigu.lt/ru/p/1", "https://pigu.lt/p/2"]
        assert sl.dominant_locale(pool) == "lt"
        assert sl.dominant_locale(pool, 0.9) is None
        assert sl.dominant_locale(["https://s.example/p/1"]) is None

    def test_keep_mask(self, engine):
        urls = ["https://pigu.lt/lt/p/1", "https://pigu.lt/ru/p/1", "https://pigu.lt/p/1"]
        assert sl.locale_keep_mask(urls, "lt") == [True, False, True]


class TestCanonicalLocaleSync:
    def _db(self, rows):
        db = MagicMock()
        db.execute.return_value.all.return_value = rows
        return db

    def test_pool_prefix_wins(self):
        rows = [("https://pigu.lt/lt/p/%d" % i,) for i in range(10)]
        with patch("app.database.sync_session_factory", lambda: self._db(rows)):
            assert sl.canonical_locale_sync(uuid4(), "EE") == "lt"

    def test_empty_pool_uses_country_language(self):
        with patch("app.database.sync_session_factory", lambda: self._db([])):
            assert sl.canonical_locale_sync(uuid4(), "EE") == "et"
            assert sl.canonical_locale_sync(uuid4(), "KZ") is None
            assert sl.canonical_locale_sync(uuid4(), None) is None

    def test_unprefixed_pool_means_no_locale(self):
        rows = [("https://s.example/p/%d" % i,) for i in range(10)]
        with patch("app.database.sync_session_factory", lambda: self._db(rows)):
            assert sl.canonical_locale_sync(uuid4(), "LT") is None
