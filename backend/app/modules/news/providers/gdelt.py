"""GDELT DOC 2.0 provider — keyless last-resort retail/business feed."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from app.config import Settings
from app.modules.market_data.http_config import (
    DEFAULT_MARKET_DATA_TIMEOUT_SECONDS,
    with_transient_retries,
)
from app.modules.news.providers.base import PROVIDER_GDELT, truncate_snippet
from app.modules.news.schemas import NewsItem

logger = logging.getLogger(__name__)

GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_MAX_RECORDS = 10


def _build_gdelt_query(*, country_code: str | None) -> str:
    """Boolean query for retail business news; optional sourcecountry filter."""
    parts = [
        '(retail OR "e-commerce" OR marketplace OR prices OR "consumer goods")',
        "business",
    ]
    if country_code:
        parts.append(f"sourcecountry:{country_code.upper()}")
    return " ".join(parts)


def _parse_gdelt_seendate(raw: str | None) -> datetime:
    if not raw:
        return datetime.now(timezone.utc)
    text = str(raw).strip()
    try:
        parsed = datetime.strptime(text[:14], "%Y%m%d%H%M%S")
        return parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        logger.warning("gdelt_unparseable_seendate value=%s", text[:20])
        return datetime.now(timezone.utc)


def map_gdelt_articles(payload: dict) -> list[NewsItem]:
    """Map GDELT DOC JSON payload to NewsItem list (unit-testable)."""
    articles = payload.get("articles")
    if not isinstance(articles, list):
        return []

    items: list[NewsItem] = []
    for row in articles:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        url = str(row.get("url") or "").strip()
        if not title or not url:
            continue
        source = str(row.get("domain") or "unknown").strip()
        snippet = truncate_snippet(title)
        image_raw = row.get("socialimage")
        image_url = str(image_raw).strip() if image_raw else None
        items.append(
            NewsItem(
                title=title,
                source=source or "unknown",
                published_at=_parse_gdelt_seendate(row.get("seendate")),
                snippet=snippet,
                url=url,
                image_url=image_url or None,
            )
        )
    return items


class GdeltProvider:
    """GDELT DOC 2.0 ArtList — always available, no API key."""

    provider_source = PROVIDER_GDELT

    def __init__(self, *, timeout: float, retry_attempts: int) -> None:
        self._timeout = timeout
        self._retry_attempts = retry_attempts

    async def fetch(
        self,
        *,
        country_code: str | None,
        language: str,
    ) -> list[NewsItem]:
        del language  # GDELT uses sourcelang param, fixed to english for feed
        params = {
            "query": _build_gdelt_query(country_code=country_code),
            "mode": "ArtList",
            "format": "json",
            "maxrecords": str(GDELT_MAX_RECORDS),
            "sourcelang": "english",
        }

        async def _request() -> list[NewsItem]:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(GDELT_DOC_URL, params=params)
                response.raise_for_status()
                payload = response.json()
            if not isinstance(payload, dict):
                return []
            return map_gdelt_articles(payload)

        try:
            return await with_transient_retries(
                _request,
                retry_attempts=self._retry_attempts,
                label="news:gdelt",
            )
        except Exception as exc:
            logger.warning("gdelt_fetch_failed err=%s", exc)
            return []


def build_gdelt_provider() -> GdeltProvider:
    """Construct keyless GDELT provider."""
    settings = Settings()
    timeout = float(settings.market_data_timeout_seconds)
    if timeout <= 0:
        timeout = DEFAULT_MARKET_DATA_TIMEOUT_SECONDS
    retry_attempts = max(0, int(settings.market_data_retry_attempts))
    return GdeltProvider(timeout=timeout, retry_attempts=retry_attempts)
