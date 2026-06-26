"""NewsData.io provider — primary retail/business feed."""

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
    PROVIDER_NEWSDATA,
    RETAIL_KEYWORDS,
    truncate_snippet,
)
from app.modules.news.schemas import NewsItem

logger = logging.getLogger(__name__)

NEWSDATA_LATEST_URL = "https://newsdata.io/api/1/latest"


def _parse_newsdata_datetime(raw: str | None) -> datetime:
    if not raw:
        return datetime.now(timezone.utc)
    text = str(raw).strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S%z",
    ):
        try:
            parsed = datetime.strptime(text.replace("Z", ""), fmt.replace("%z", ""))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        logger.warning("newsdata_unparseable_date value=%s", text[:40])
        return datetime.now(timezone.utc)


def map_newsdata_results(payload: dict) -> list[NewsItem]:
    """Map NewsData.io JSON payload to NewsItem list (unit-testable)."""
    results = payload.get("results")
    if not isinstance(results, list):
        return []

    items: list[NewsItem] = []
    for row in results:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        url = str(row.get("link") or row.get("url") or "").strip()
        if not title or not url:
            continue
        source = str(row.get("source_id") or row.get("source") or "unknown").strip()
        snippet = truncate_snippet(str(row.get("description") or ""))
        image_raw = row.get("image_url") or row.get("image")
        image_url = str(image_raw).strip() if image_raw else None
        items.append(
            NewsItem(
                title=title,
                source=source or "unknown",
                published_at=_parse_newsdata_datetime(row.get("pubDate")),
                snippet=snippet,
                url=url,
                image_url=image_url or None,
            )
        )
    return items


class NewsDataProvider:
    """NewsData.io latest endpoint — skipped when api key is absent."""

    provider_source = PROVIDER_NEWSDATA

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
            "apikey": self._api_key,
            "category": "business",
            "language": language.lower()[:5],
            "q": RETAIL_KEYWORDS,
        }
        if country_code:
            params["country"] = country_code.lower()

        async def _request() -> list[NewsItem]:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(NEWSDATA_LATEST_URL, params=params)
                response.raise_for_status()
                payload = response.json()
            if not isinstance(payload, dict):
                return []
            if str(payload.get("status", "")).lower() not in ("success", "ok"):
                logger.warning(
                    "newsdata_non_success status=%s",
                    payload.get("status"),
                )
                return []
            return map_newsdata_results(payload)

        try:
            return await with_transient_retries(
                _request,
                retry_attempts=self._retry_attempts,
                label="news:newsdata",
            )
        except Exception as exc:
            logger.warning("newsdata_fetch_failed err=%s", exc)
            return []


def build_newsdata_provider() -> NewsDataProvider | None:
    """Construct provider when NEWSDATA_API_KEY is configured."""
    settings = Settings()
    if not settings.newsdata_api_key:
        return None
    timeout = float(settings.market_data_timeout_seconds)
    if timeout <= 0:
        timeout = DEFAULT_MARKET_DATA_TIMEOUT_SECONDS
    retry_attempts = max(0, int(settings.market_data_retry_attempts))
    return NewsDataProvider(
        settings.newsdata_api_key,
        timeout=timeout,
        retry_attempts=retry_attempts,
    )
