"""Redis TTL cache for news responses (transient external content)."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.config import Settings
from app.modules.news.schemas import NewsResponse

logger = logging.getLogger(__name__)

_redis_client: Any | None = None


def _get_redis() -> Any:
    """Lazy Redis client (same pattern as proxy_provider_limiter)."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    import redis

    settings = Settings()
    _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def build_cache_key(*, country_code: str | None, language: str) -> str:
    """Stable Redis key for a scoped news feed."""
    scope = (country_code or "all").lower()
    lang = language.lower()[:5]
    return f"news:{scope}:{lang}"


async def get_cached(key: str) -> NewsResponse | None:
    """Return cached NewsResponse or None on miss / Redis failure."""
    try:
        client = _get_redis()
        raw = client.get(key)
    except Exception as exc:
        logger.warning("news_cache_get_failed key=%s err=%s", key, exc)
        return None
    if not raw:
        return None
    try:
        payload = json.loads(raw)
        return NewsResponse.model_validate(payload)
    except Exception as exc:
        logger.warning("news_cache_deserialize_failed key=%s err=%s", key, exc)
        return None


async def set_cached(key: str, value: NewsResponse, ttl: int) -> None:
    """Best-effort cache write; logs and swallows Redis errors."""
    if ttl <= 0:
        return
    try:
        client = _get_redis()
        client.setex(key, ttl, value.model_dump_json())
    except Exception as exc:
        logger.warning("news_cache_set_failed key=%s err=%s", key, exc)
