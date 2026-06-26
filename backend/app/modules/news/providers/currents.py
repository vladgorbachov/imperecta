"""Currents API provider — fallback retail/business feed."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from app.config import Settings
from app.modules.market_data.http_config import (
    DEFAULT_MARKET_DATA_TIMEOUT_SECONDS,
    with_transient_retries,
)
from app.modules.news.providers.base import (
    PROVIDER_CURRENTS,
    RETAIL_KEYWORDS,
    truncate_snippet,
)
from app.modules.news.schemas import NewsItem

logger = logging.getLogger(__name__)

CURRENTS_SEARCH_URL = "https://api.currentsapi.services/v1/search"


def _parse_currents_datetime(raw: str | None) -> datetime:
    if not raw:
        return datetime.now(timezone.utc)
    text = str(raw).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        logger.warning("currents_unparseable_date value=%s", text[:40])
        return datetime.now(timezone.utc)


def map_currents_results(payload: dict) -> list[NewsItem]:
    """Map Currents API JSON payload to NewsItem list (unit-testable)."""
    news = payload.get("news")
    if not isinstance(news, list):
        return []

    items: list[NewsItem] = []
    for row in news:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        url = str(row.get("url") or "").strip()
        if not title or not url:
            continue
        source = str(row.get("author") or row.get("source") or "unknown").strip()
        snippet = truncate_snippet(str(row.get("description") or ""))
        image_raw = row.get("image")
        image_url = str(image_raw).strip() if image_raw else None
        items.append(
            NewsItem(
                title=title,
                source=source or "unknown",
                published_at=_parse_currents_datetime(row.get("published")),
                snippet=snippet,
                url=url,
                image_url=image_url or None,
            )
        )
    return items


class CurrentsProvider:
    """Currents search endpoint — skipped when api key is absent."""

    provider_source = PROVIDER_CURRENTS

    def __init__(self, api_key: str, *, timeout: float, retry_attempts: int) -> None:
        self._api_key = api_key
        self._timeout = timeout
        self._retry_attempts = retry_attempts

    async def fetch(
        self,
        *,
        country_code: str | None,
        language: str,
    ) -> list[NewsItem]:
        params: dict[str, str] = {
            "category": "business",
            "language": language.lower()[:5],
            "keywords": RETAIL_KEYWORDS,
        }
        if country_code:
            params["country"] = country_code.upper()
        headers = {"Authorization": self._api_key}

        async def _request() -> list[NewsItem]:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    CURRENTS_SEARCH_URL,
                    params=params,
                    headers=headers,
                )
                response.raise_for_status()
                payload = response.json()
            if not isinstance(payload, dict):
                return []
            if str(payload.get("status", "")).lower() not in ("ok", "success"):
                logger.warning(
                    "currents_non_success status=%s",
                    payload.get("status"),
                )
                return []
            return map_currents_results(payload)

        try:
            return await with_transient_retries(
                _request,
                retry_attempts=self._retry_attempts,
                label="news:currents",
            )
        except Exception as exc:
            logger.warning("currents_fetch_failed err=%s", exc)
            return []


def build_currents_provider() -> CurrentsProvider | None:
    """Construct provider when CURRENTS_API_KEY is configured."""
    settings = Settings()
    if not settings.currents_api_key:
        return None
    timeout = float(settings.market_data_timeout_seconds)
    if timeout <= 0:
        timeout = DEFAULT_MARKET_DATA_TIMEOUT_SECONDS
    retry_attempts = max(0, int(settings.market_data_retry_attempts))
    return CurrentsProvider(
        settings.currents_api_key,
        timeout=timeout,
        retry_attempts=retry_attempts,
    )
