"""Cross-process proxy-provider outbound rate limiter (fleet-wide token bucket on Redis)."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.config import Settings

PROXY_PROVIDER_REDIS_KEY = "proxy_provider:ratebucket"
PROXY_PROVIDER_DEADLINE_ERROR = "proxy_provider_deadline"

# Concurrent in-flight fetches per scrape child (tunable; provider cap is fleet-wide).
SCRAPE_FETCH_PARALLELISM = 5

# Fail-closed fallback when Redis is unreachable: at most one provider token per
# second per process (2 workers -> <=2 req/s, conservative vs configured RPS).
_LOCAL_FALLBACK_MIN_INTERVAL_SEC = 1.0


def proxy_provider_max_rps() -> int:
    """Fleet-wide proxy-provider requests-per-second cap (from settings)."""
    return Settings().proxy_provider_rps


def proxy_provider_bucket_capacity() -> int:
    """Token-bucket capacity equals RPS (unchanged contract from Stage 1b)."""
    return Settings().proxy_provider_rps

_ACQUIRE_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])
local capacity = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])

local data = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(data[1])
local last_refill = tonumber(data[2])

if tokens == nil then
  tokens = capacity
  last_refill = now
end

local elapsed = math.max(0, now - last_refill) / 1000.0
tokens = math.min(capacity, tokens + elapsed * rate)

if tokens < requested then
  redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
  redis.call('PEXPIRE', key, 120000)
  return 0
end

tokens = tokens - requested
redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
redis.call('PEXPIRE', key, 120000)
return 1
"""

_redis_client: Any | None = None
_local_fallback_lock = asyncio.Lock()
_local_fallback_last_monotonic = 0.0


def _get_redis() -> Any:
    """Lazy Redis client (same pattern as worker_log_relay)."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    import redis

    settings = Settings()
    _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def _deadline_remaining(deadline_monotonic: float | None) -> float | None:
    if deadline_monotonic is None:
        return None
    return deadline_monotonic - time.monotonic()


async def _acquire_local_fallback(deadline_monotonic: float | None) -> bool:
    """Serialize provider attempts at 1/s per process when Redis is down."""
    global _local_fallback_last_monotonic
    async with _local_fallback_lock:
        now = time.monotonic()
        wait_sec = max(
            0.0,
            _LOCAL_FALLBACK_MIN_INTERVAL_SEC - (now - _local_fallback_last_monotonic),
        )
        remaining = _deadline_remaining(deadline_monotonic)
        if remaining is not None and wait_sec > remaining:
            return False
        if wait_sec > 0:
            await asyncio.sleep(wait_sec)
        _local_fallback_last_monotonic = time.monotonic()
        return True


def _redis_acquire_sync() -> bool:
    client = _get_redis()
    now_ms = int(time.time() * 1000)
    max_rps = proxy_provider_max_rps()
    bucket_capacity = proxy_provider_bucket_capacity()
    result = client.eval(
        _ACQUIRE_LUA,
        1,
        PROXY_PROVIDER_REDIS_KEY,
        now_ms,
        max_rps,
        bucket_capacity,
        1,
    )
    return int(result) == 1


async def acquire_proxy_provider_token(deadline_monotonic: float | None = None) -> bool:
    """Acquire one proxy-provider outbound token before issuing a provider POST.

    Returns False when the cooperative deadline would be exceeded by waiting,
    or when Redis is unavailable and the local fail-closed fallback cannot
    obtain a slot in time. True when a token was granted.
    """
    remaining = _deadline_remaining(deadline_monotonic)
    if remaining is not None and remaining <= 0:
        return False

    try:
        acquired = await asyncio.to_thread(_redis_acquire_sync)
        if acquired:
            return True
        wait_sec = 1.0 / proxy_provider_max_rps()
        if remaining is not None and wait_sec > remaining:
            return False
        await asyncio.sleep(wait_sec)
        if _deadline_remaining(deadline_monotonic) is not None:
            if _deadline_remaining(deadline_monotonic) <= 0:
                return False
        acquired = await asyncio.to_thread(_redis_acquire_sync)
        return acquired
    except Exception:
        return await _acquire_local_fallback(deadline_monotonic)


def reset_limiter_state_for_tests() -> None:
    """Clear module-level Redis handle and local fallback clock (tests only)."""
    global _redis_client, _local_fallback_last_monotonic
    _redis_client = None
    _local_fallback_last_monotonic = 0.0
