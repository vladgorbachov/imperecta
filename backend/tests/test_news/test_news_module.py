"""Unit tests for the news module (DB-free, no live API keys)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.news import cache as news_cache
from app.modules.news.normalize import (
    clean_snippet,
    dedup_key,
    is_junk,
    is_retail_relevant,
    normalize_feed,
)
from app.modules.news.provider_queue import fetch_news_chain
from app.modules.news.providers.base import (
    PROVIDER_CURRENTS,
    PROVIDER_GDELT,
    PROVIDER_NEWSDATA,
    RETAIL_KEYWORDS,
    truncate_snippet,
)
from app.modules.news.providers.currents import map_currents_results
from app.modules.news.providers.gdelt import map_gdelt_articles
from app.modules.news.providers.newsdata import map_newsdata_results
from app.modules.news.schemas import NewsItem, NewsResponse
from app.modules.news.service import _build_provider_list, get_news


def _ts() -> datetime:
    return datetime(2026, 6, 25, 12, 0, 0, tzinfo=timezone.utc)


class _StubProvider:
    def __init__(self, source: str, items: list[NewsItem]) -> None:
        self._source = source
        self._items = items
        self.fetch = AsyncMock(return_value=items)

    @property
    def provider_source(self) -> str:
        return self._source


def test_retail_keywords_within_newsdata_limit() -> None:
    assert len(RETAIL_KEYWORDS) <= 100


def test_truncate_snippet_caps_length() -> None:
    long_text = "word " * 80
    result = truncate_snippet(long_text)
    assert len(result) <= 240


def test_map_newsdata_results_fixture() -> None:
    payload = {
        "status": "success",
        "results": [
            {
                "title": "Retail growth in EU",
                "link": "https://example.com/a",
                "description": "E-commerce marketplace prices shift.",
                "pubDate": "2026-06-25 10:00:00",
                "source_id": "Example News",
                "image_url": "https://example.com/img.jpg",
            }
        ],
    }
    items = map_newsdata_results(payload)
    assert len(items) == 1
    assert items[0].title == "Retail growth in EU"
    assert items[0].source == "Example News"
    assert items[0].url == "https://example.com/a"
    assert items[0].image_url == "https://example.com/img.jpg"
    assert items[0].published_at.year == 2026


def test_map_currents_results_fixture() -> None:
    payload = {
        "status": "ok",
        "news": [
            {
                "title": "Consumer goods prices",
                "description": "Retail sector update.",
                "url": "https://example.com/b",
                "published": "2026-06-25T10:00:00Z",
                "author": "Wire Service",
                "image": "https://example.com/b.jpg",
            }
        ],
    }
    items = map_currents_results(payload)
    assert len(items) == 1
    assert items[0].source == "Wire Service"
    assert items[0].snippet == "Retail sector update."


def test_map_gdelt_articles_fixture() -> None:
    payload = {
        "articles": [
            {
                "title": "Marketplace retail trends",
                "url": "https://example.com/c",
                "seendate": "20260625100000",
                "domain": "retail.example",
                "socialimage": "https://example.com/c.jpg",
            }
        ],
    }
    items = map_gdelt_articles(payload)
    assert len(items) == 1
    assert items[0].source == "retail.example"
    assert items[0].snippet == "Marketplace retail trends"


def test_clean_snippet_removes_duplicate_read_more_tail() -> None:
    raw = (
        "Retail prices shift across EU marketplaces. "
        "Read more at straitstimes.com. Read more at straitstimes.com."
    )
    once = clean_snippet(raw)
    twice = clean_snippet(once)
    assert once == twice
    assert once.count("Read more at straitstimes.com") == 1


def test_clean_snippet_is_idempotent_on_whitespace() -> None:
    raw = "E-commerce   retail   update."
    once = clean_snippet(raw)
    twice = clean_snippet(once)
    assert once == twice
    assert once == "E-commerce retail update."


def test_is_junk_company_announcements_title() -> None:
    item = NewsItem(
        title="Company Announcements",
        source="Reuters",
        published_at=_ts(),
        snippet="Board meeting notes.",
        url="https://example.com/a",
    )
    assert is_junk(item) is True


def test_is_junk_feedloader_source() -> None:
    item = NewsItem(
        title="Retail update",
        source="Feedloaderapi",
        published_at=_ts(),
        snippet="Marketplace prices in EU retail.",
        url="https://example.com/b",
    )
    assert is_junk(item) is True


def test_is_junk_feed_stub_snippet() -> None:
    item = NewsItem(
        title="Fund facts",
        source="Example",
        published_at=_ts(),
        snippet=(
            "The latest company information, including net asset values "
            "and dividend dates."
        ),
        url="https://example.com/c",
    )
    assert is_junk(item) is True


def test_is_retail_relevant_positive() -> None:
    item = NewsItem(
        title="EU retail outlook",
        source="Wire",
        published_at=_ts(),
        snippet="Shoppers face higher basket prices.",
        url="https://example.com/d",
    )
    assert is_retail_relevant(item) is True


def test_is_retail_relevant_negative() -> None:
    item = NewsItem(
        title="SpaceX lifts Nasdaq 100",
        source="Wire",
        published_at=_ts(),
        snippet="Dividend payouts and protests in the capital.",
        url="https://example.com/e",
    )
    assert is_retail_relevant(item) is False


def test_dedup_key_url_and_title() -> None:
    left = NewsItem(
        title="Retail prices rise",
        source="Wire",
        published_at=_ts(),
        snippet="E-commerce marketplace update.",
        url="https://Example.com/a?utm_source=x",
    )
    right = NewsItem(
        title="Retail prices rise!",
        source="Wire",
        published_at=_ts(),
        snippet="Another snippet.",
        url="https://example.com/a/",
    )
    assert dedup_key(left)[0] == dedup_key(right)[0]
    assert dedup_key(left)[1] == dedup_key(right)[1]


def test_normalize_feed_end_to_end() -> None:
    retail = NewsItem(
        title="Retail prices rise in EU",
        source="Retail Wire",
        published_at=_ts(),
        snippet="Online store checkout prices shift for consumer goods.",
        url="https://example.com/retail",
    )
    duplicate = NewsItem(
        title="Retail prices rise in EU",
        source="Retail Wire",
        published_at=_ts(),
        snippet="Duplicate headline only.",
        url="https://example.com/other",
    )
    junk = NewsItem(
        title="Company Announcements",
        source="Nbuffie",
        published_at=_ts(),
        snippet="The latest company information, including net asset values.",
        url="https://example.com/junk",
    )
    off_topic = NewsItem(
        title="SpaceX lifts Nasdaq 100",
        source="Markets",
        published_at=_ts(),
        snippet="Dividend payouts rise after protests.",
        url="https://example.com/spacex",
    )
    snippet_dup = NewsItem(
        title="Marketplace discount sales",
        source="Shop News",
        published_at=_ts(),
        snippet=(
            "Retail basket update. Read more at straitstimes.com. "
            "Read more at straitstimes.com."
        ),
        url="https://example.com/sales",
    )

    result = normalize_feed([retail, duplicate, junk, off_topic, snippet_dup])
    assert len(result) == 2
    assert result[0].title == "Retail prices rise in EU"
    assert result[1].title == "Marketplace discount sales"
    assert result[1].snippet.count("Read more at straitstimes.com") == 1


@pytest.mark.asyncio
async def test_fetch_news_chain_first_non_empty_wins() -> None:
    winner = NewsItem(
        title="Headline",
        source="src",
        published_at=_ts(),
        snippet="snippet",
        url="https://example.com",
    )
    providers = [
        _StubProvider(PROVIDER_NEWSDATA, []),
        _StubProvider(PROVIDER_CURRENTS, [winner]),
        _StubProvider(PROVIDER_GDELT, [winner]),
    ]
    items, source = await fetch_news_chain(
        providers,
        country_code="MD",
        language="en",
    )
    assert len(items) == 1
    assert source == PROVIDER_CURRENTS
    providers[2].fetch.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_news_chain_all_empty() -> None:
    providers = [
        _StubProvider(PROVIDER_NEWSDATA, []),
        _StubProvider(PROVIDER_CURRENTS, []),
    ]
    items, source = await fetch_news_chain(
        providers,
        country_code=None,
        language="en",
    )
    assert items == []
    assert source == ""


@pytest.mark.asyncio
async def test_fetch_news_chain_skips_failing_provider() -> None:
    winner = NewsItem(
        title="GDELT headline",
        source="gdelt.example",
        published_at=_ts(),
        snippet="snippet",
        url="https://example.com/g",
    )
    failing = _StubProvider(PROVIDER_NEWSDATA, [])
    failing.fetch = AsyncMock(side_effect=RuntimeError("down"))
    providers = [
        failing,
        _StubProvider(PROVIDER_GDELT, [winner]),
    ]
    items, source = await fetch_news_chain(
        providers,
        country_code=None,
        language="en",
    )
    assert len(items) == 1
    assert source == PROVIDER_GDELT


@pytest.mark.asyncio
async def test_cache_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    store: dict[str, str] = {}
    fake = MagicMock()

    def _get(key: str) -> str | None:
        return store.get(key)

    def _setex(key: str, ttl: int, value: str) -> None:
        store[key] = value

    fake.get.side_effect = _get
    fake.setex.side_effect = _setex
    monkeypatch.setattr(news_cache, "_get_redis", lambda: fake)

    response = NewsResponse(
        items=[
            NewsItem(
                title="Cached",
                source="src",
                published_at=_ts(),
                snippet="snip",
                url="https://example.com",
            )
        ],
        source_provider=PROVIDER_NEWSDATA,
    )
    key = news_cache.build_cache_key(country_code="MD", language="en")
    await news_cache.set_cached(key, response, ttl=1200)
    loaded = await news_cache.get_cached(key)
    assert loaded is not None
    assert loaded.source_provider == PROVIDER_NEWSDATA
    assert len(loaded.items) == 1
    assert loaded.items[0].title == "Cached"
    raw = json.loads(store[key])
    assert raw["source_provider"] == PROVIDER_NEWSDATA


@pytest.mark.asyncio
async def test_cache_get_returns_none_on_redis_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        news_cache,
        "_get_redis",
        lambda: (_ for _ in ()).throw(ConnectionError("down")),
    )
    result = await news_cache.get_cached("news:all:en")
    assert result is None


def test_build_provider_list_always_includes_gdelt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    monkeypatch.setattr(
        "app.modules.news.service.Settings",
        lambda: SimpleNamespace(
            newsdata_api_key=None,
            currents_api_key=None,
            market_data_timeout_seconds=15,
            market_data_retry_attempts=0,
        ),
    )
    monkeypatch.setattr(
        "app.modules.news.providers.gdelt.Settings",
        lambda: SimpleNamespace(
            market_data_timeout_seconds=15,
            market_data_retry_attempts=0,
        ),
    )
    providers = _build_provider_list()
    assert len(providers) == 1
    assert providers[0].provider_source == PROVIDER_GDELT


def test_build_cache_key() -> None:
    assert news_cache.build_cache_key(country_code=None, language="en") == "news:all:en"
    assert news_cache.build_cache_key(country_code="MD", language="en") == "news:md:en"


@pytest.mark.asyncio
async def test_get_news_returns_cache_hit_without_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cached = NewsResponse(
        items=[
            NewsItem(
                title="From cache",
                source="src",
                published_at=_ts(),
                snippet="snip",
                url="https://example.com",
            )
        ],
        source_provider=PROVIDER_NEWSDATA,
    )
    monkeypatch.setattr(
        news_cache,
        "get_cached",
        AsyncMock(return_value=cached),
    )
    chain_mock = AsyncMock()
    monkeypatch.setattr("app.modules.news.service.fetch_news_chain", chain_mock)

    result = await get_news(country_code="MD", language="en")
    assert result.source_provider == PROVIDER_NEWSDATA
    chain_mock.assert_not_called()


@pytest.mark.asyncio
async def test_get_news_does_not_cache_empty_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(news_cache, "get_cached", AsyncMock(return_value=None))
    monkeypatch.setattr(
        "app.modules.news.service.fetch_news_chain",
        AsyncMock(return_value=([], "")),
    )
    set_mock = AsyncMock()
    monkeypatch.setattr(news_cache, "set_cached", set_mock)

    result = await get_news(country_code=None, language="en")
    assert result.items == []
    assert result.source_provider == ""
    set_mock.assert_not_called()
