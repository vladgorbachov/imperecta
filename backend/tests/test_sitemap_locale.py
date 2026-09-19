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

    def test_noise_sitemap(self, engine):
        assert sl.is_noise_sitemap("https://pigu.lt/lt/sitemap-products-images-3.xml")
        assert sl.is_noise_sitemap("https://s.example/sitemap_video.xml")
        assert sl.is_noise_sitemap("https://sitemap.tsbohemia.cz/cs/sitemap-products-disabled-12-cs.xml")
        assert sl.is_noise_sitemap("https://sitemap.tsbohemia.cz/cs/sitemap-products-disabled-consultations-1-cs.xml")
        assert sl.is_noise_sitemap("https://sitemap.tsbohemia.cz/cs/sitemap-products-reviews-1-cs.xml")
        assert sl.is_noise_sitemap("https://pigu.lt/lt/sitemap-archive-visible-products-1.xml")
        assert not sl.is_noise_sitemap("https://pigu.lt/lt/sitemap-products-3.xml")
        assert not sl.is_noise_sitemap("https://sitemap.tsbohemia.cz/cs/sitemap-products-accessories-3-cs.xml")
        assert not sl.is_noise_sitemap("https://s.example/sitemap-news.xml")

    def test_whole_tree_with_pool_locale(self, engine):
        sel = sl.select_sitemap_subfiles(PIGU_INDEX, "lt", "lt", whole_tree=True)
        assert sel.kept == ["https://pigu.lt/lt/sitemap-products-1.xml", "https://pigu.lt/sitemap-general.xml"]
        assert sel.skipped_noise == 2 and sel.skipped_locale == 2 and sel.locale == "lt"

    def test_whole_tree_country_hint_then_first(self, engine):
        # ru is never elected while another language exists (WP11.4)
        assert sl.select_sitemap_subfiles(PIGU_INDEX, None, "ru", whole_tree=True).locale == "lt"
        assert sl.select_sitemap_subfiles(PIGU_INDEX, None, "et", whole_tree=True).locale == "lt"
        # a canonical the index lacks falls through to the hint, a ru hint to the first eligible
        assert sl.select_sitemap_subfiles(PIGU_INDEX, "en", "ru", whole_tree=True).locale == "lt"
        both = ["https://s.example/lv/a.xml", "https://s.example/ru/a.xml", "https://s.example/et/a.xml"]
        assert sl.select_sitemap_subfiles(both, "ru", None, whole_tree=True).locale == "lv"
        # ru-only trees stay ru: that is the shop's data
        ru_only = ["https://s.example/ru/a.xml", "https://s.example/ru-ua/b.xml"]
        assert sl.select_sitemap_subfiles(ru_only, None, None, whole_tree=True).locale == "ru"

    def test_whole_tree_single_locale_untouched(self, engine):
        files = ["https://s.example/lt/a.xml", "https://s.example/lt/b.xml", "https://s.example/c.xml"]
        sel = sl.select_sitemap_subfiles(files, "ru", "ru", whole_tree=True)
        assert sel.kept == files and sel.locale is None

    def test_shard_canonical_is_authoritative(self, engine):
        ru_only = ["https://pigu.lt/ru/sitemap-products-7.xml", "https://pigu.lt/ru/sitemap-products-8.xml"]
        sel = sl.select_sitemap_subfiles(ru_only, "lt", "lt")
        assert sel.kept == [] and sel.skipped_locale == 2 and sel.locale == "lt"
        own = ["https://pigu.lt/lt/sitemap-products-7.xml", "https://pigu.lt/sitemap-general.xml"]
        sel = sl.select_sitemap_subfiles(own, "lt", "lt")
        assert sel.kept == own and sel.locale is None

    def test_shard_without_canonical_drops_nothing(self, engine):
        # the country hint alone never lets a shard elect a locale
        isolated = sl.select_sitemap_subfiles(PIGU_INDEX, None, "lt")
        assert isolated.locale is None and isolated.skipped_locale == 0
        assert len(isolated.kept) == 4 and isolated.skipped_noise == 2

    def test_dominant_locale_threshold(self, engine):
        pool = ["https://pigu.lt/lt/p/%d" % i for i in range(8)] + ["https://pigu.lt/ru/p/1", "https://pigu.lt/p/2"]
        assert sl.dominant_locale(pool) == "lt"
        assert sl.dominant_locale(pool, 0.9) is None
        assert sl.dominant_locale(["https://s.example/p/1"]) is None

    def test_whole_tree_pool_prefix_outside_file_space_is_ignored(self, engine):
        """tsbohemia: files under /cs/, pool under /en/ (hreflang) — one
        locale in the index, nothing is dropped."""
        files = ["https://sitemap.tsbohemia.cz/cs/sitemap-products-%d-cs.xml" % i for i in range(3)]
        sel = sl.select_sitemap_subfiles(files, "en", "cs", whole_tree=True)
        assert sel.kept == files and sel.locale is None and sel.skipped_locale == 0


class TestCanonicalLocaleSync:
    def _db(self, rows):
        db = MagicMock()
        db.execute.return_value.all.return_value = rows
        return db

    def test_pool_prefix_wins(self):
        rows = [("https://pigu.lt/lt/p/%d" % i,) for i in range(10)]
        with patch("app.database.sync_session_factory", lambda: self._db(rows)):
            assert sl.canonical_locale_sync(uuid4()) == "lt"

    def test_empty_pool_is_unknown_not_guessed(self):
        """The country language is a whole-tree tie-breaker, never a
        canonical a shard could drop files against."""
        with patch("app.database.sync_session_factory", lambda: self._db([])):
            assert sl.canonical_locale_sync(uuid4()) is None
        assert sl.country_language_hint("EE") == "et"
        assert sl.country_language_hint("CH") is None
        assert sl.country_language_hint(None) is None

    def test_unprefixed_pool_means_no_locale(self):
        rows = [("https://s.example/p/%d" % i,) for i in range(10)]
        with patch("app.database.sync_session_factory", lambda: self._db(rows)):
            assert sl.canonical_locale_sync(uuid4()) is None
