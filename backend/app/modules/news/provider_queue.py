"""Provider chain — first non-empty feed wins."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from app.modules.news.providers.base import NewsProvider
from app.modules.news.schemas import NewsItem

logger = logging.getLogger(__name__)


async def fetch_news_chain(
    providers: Sequence[NewsProvider],
    *,
    country_code: str | None,
    language: str,
) -> tuple[list[NewsItem], str]:
    """Try providers in order; return first non-empty result and its source id."""
    for provider in providers:
        try:
            items = await provider.fetch(
                country_code=country_code,
                language=language,
            )
        except Exception as exc:
            logger.warning(
                "news_provider_fetch_failed source=%s err=%s",
                provider.provider_source,
                exc,
            )
            continue
        if items:
            return items, provider.provider_source
    return [], ""
