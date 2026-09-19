"""Per-user request budgets on read routes (legal clean-up WP2).

Fixed one-hour windows on Redis: one INCR + EXPIRE per request, O(1), one
key per (scope, user, hour). Redis unreachable → the request passes and the
outage is logged once per process (availability over the guard; the page
and depth caps still bound every response). WP10 replaces this with the
read-metering door and per-plan budgets.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import structlog
from fastapi import Depends, HTTPException, Request

from app.common.deps import CurrentUser
from app.config import Settings

slog = structlog.get_logger(__name__)

_WINDOW_SEC = 3600
_redis_client: Any | None = None
_redis_down_logged = False


def _get_async_redis() -> Any:
    global _redis_client
    if _redis_client is None:
        import redis.asyncio as redis_async

        _redis_client = redis_async.from_url(Settings().redis_url, decode_responses=True)
    return _redis_client


def rate_limit_key(scope: str, user_id: str, now: float | None = None) -> str:
    window = int((now if now is not None else time.time()) // _WINDOW_SEC)
    return f"ratelimit:{scope}:{user_id}:{window}"


async def consume(scope: str, user_id: str, limit: int) -> tuple[bool, int]:
    """Count one request; returns (allowed, remaining)."""
    global _redis_down_logged
    key = rate_limit_key(scope, user_id)
    try:
        client = _get_async_redis()
        pipe = client.pipeline(transaction=True)
        pipe.incr(key)
        pipe.expire(key, _WINDOW_SEC)
        used, _ = await pipe.execute()
    except Exception as exc:  # noqa: BLE001 - fail open, log once
        if not _redis_down_logged:
            _redis_down_logged = True
            slog.warning("rate_limit_redis_unavailable", scope=scope, error=str(exc)[:200])
        return True, limit
    used = int(used)
    return used <= limit, max(0, limit - used)


def user_rate_limit(scope: str, limit_getter: Callable[[], int]) -> Callable:
    """Dependency factory: `Depends(user_rate_limit("pool", lambda: settings.x))`."""

    async def _dependency(request: Request, current_user: CurrentUser) -> None:
        limit = int(limit_getter())
        if limit <= 0:
            return
        allowed, remaining = await consume(scope, str(current_user.id), limit)
        request.state.rate_limit_remaining = remaining
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="rate_limited",
                headers={"Retry-After": str(_WINDOW_SEC)},
            )

    return _dependency


__all__ = ["consume", "rate_limit_key", "user_rate_limit"]
