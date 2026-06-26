"""News orchestration — Redis cache + provider chain."""

from __future__ import annotations

import structlog

from app.config import Settings
from app.modules.news import cache as news_cache
from app.modules.news.provider_queue import fetch_news_chain
from app.modules.news.providers.base import NewsProvider
from app.modules.news.providers.currents import build_currents_provider
from app.modules.news.providers.gdelt import build_gdelt_provider
from app.modules.news.providers.newsdata import build_newsdata_provider
from app.modules.news.schemas import NewsResponse

slog = structlog.get_logger(__name__)


def _build_provider_list() -> list[NewsProvider]:
    providers: list[NewsProvider] = []
    newsdata = build_newsdata_provider()
    if newsdata is not None:
        providers.append(newsdata)
    currents = build_currents_provider()
    if currents is not None:
        providers.append(currents)
    providers.append(build_gdelt_provider())
    return providers


async def get_news(
    *,
    country_code: str | None,
    language: str = "en",
) -> NewsResponse:
    """Return cached or freshly fetched headlines; never fabricates content."""
    settings = Settings()
    cache_key = news_cache.build_cache_key(
        country_code=country_code,
        language=language,
    )

    cached = await news_cache.get_cached(cache_key)
    if cached is not None:
        slog.info(
            "news_cache_hit",
            cache_key=cache_key,
            source_provider=cached.source_provider,
            count=len(cached.items),
        )
        return cached

    providers = _build_provider_list()
    items, source_provider = await fetch_news_chain(
        providers,
        country_code=country_code,
        language=language,
    )
    response = NewsResponse(items=items, source_provider=source_provider)

    if items:
        await news_cache.set_cached(
            cache_key,
            response,
            settings.news_cache_ttl_seconds,
        )
        slog.info(
            "news_fetched",
            cache_key=cache_key,
            source_provider=source_provider,
            count=len(items),
        )
    else:
        slog.warning(
            "news_all_providers_empty",
            cache_key=cache_key,
            provider_count=len(providers),
        )

    return response
