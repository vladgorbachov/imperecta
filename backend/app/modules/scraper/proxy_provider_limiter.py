"""Cross-process proxy-provider outbound rate limiter (fleet-wide token bucket on Redis)."""

from __future__ import annotations

import asyncio
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.config import Settings

PROXY_PROVIDER_REDIS_KEY = "proxy_provider:ratebucket"
PROXY_PROVIDER_DEADLINE_ERROR = "proxy_provider_deadline"
PROXY_PROVIDER_BUDGET_ERROR = "proxy_provider_budget"
# Infrastructure skips, not verdicts about the listing: the fetch never
# happened, so callers must not count them toward failure streaks.
PROXY_PROVIDER_SKIP_ERRORS = frozenset(
    {PROXY_PROVIDER_DEADLINE_ERROR, PROXY_PROVIDER_BUDGET_ERROR}
)

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


# Daily usage counters for the real-cost report (roadmap item 1): every
# granted token increments proxy_provider:usage:<YYYYMMDD>. Best-effort —
# an accounting failure never blocks a scrape; billing truth stays with the
# provider's own dashboard, this is the operational estimate.
PROXY_USAGE_KEY_PREFIX = "proxy_provider:usage:"
_USAGE_TTL_SECONDS = 90 * 24 * 3600


def _record_usage_sync() -> None:
    try:
        client = _get_redis()
        key = PROXY_USAGE_KEY_PREFIX + time.strftime("%Y%m%d", time.gmtime())
        client.incr(key)
        client.expire(key, _USAGE_TTL_SECONDS)
    except Exception:  # noqa: BLE001 - accounting must never fail a fetch
        pass


def proxy_provider_daily_cap() -> int:
    """Optional hard per-day ceiling on top of the budget; 0 = budget only."""
    return int(Settings().proxy_provider_daily_cap or 0)


def proxy_provider_monthly_cap() -> int:
    """Requests the monthly budget buys at the configured per-1k price (0 = unlimited)."""
    settings = Settings()
    budget = float(settings.proxy_provider_monthly_budget_usd or 0)
    cost = float(settings.proxy_cost_per_1k_usd or 0)
    if budget <= 0 or cost <= 0:
        return 0
    return int(budget / cost * 1000)


def billing_cycle(now: float | None = None) -> tuple[date, date]:
    """[start, end) of the provider billing cycle containing `now` (UTC).

    The cycle renews on proxy_provider_billing_day of each month (Decodo:
    the 16th); a renewal day past the month's length clamps to its last day.
    """
    import calendar

    today = datetime.fromtimestamp(now if now is not None else time.time(), tz=timezone.utc).date()
    renew_day = int(Settings().proxy_provider_billing_day or 1)

    def _renewal(year: int, month: int) -> date:
        return date(year, month, min(renew_day, calendar.monthrange(year, month)[1]))

    this_month = _renewal(today.year, today.month)
    if today >= this_month:
        start = this_month
        ny, nm = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
        end = _renewal(ny, nm)
    else:
        py, pm = (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)
        start = _renewal(py, pm)
        end = this_month
    return start, end


def budget_status_sync(now: float | None = None) -> dict:
    """Budget view for the guard and the admin report.

    The budget is per BILLING CYCLE (unused balance is lost at renewal), so
    the guard spreads what is left of the cycle evenly over the days that
    remain: an overspent day (2026-09-18: 4,891 requests in one enumeration
    burst) tightens the following ones instead of blowing the cycle. Keys:
      monthly_cap, month_used, today_used, daily_allowance, exhausted,
      cycle_start, cycle_end, days_left.
    """
    ts = now if now is not None else time.time()
    today = datetime.fromtimestamp(ts, tz=timezone.utc).date()
    today_key = today.strftime("%Y%m%d")
    monthly_cap = proxy_provider_monthly_cap()
    hard_daily = proxy_provider_daily_cap()
    cycle_start, cycle_end = billing_cycle(ts)
    client = _get_redis()
    day_count = (today - cycle_start).days + 1
    month_keys = [
        PROXY_USAGE_KEY_PREFIX + (cycle_start + timedelta(days=i)).strftime("%Y%m%d")
        for i in range(day_count)
    ]
    values = client.mget(month_keys)
    per_day = [int(v) if v else 0 for v in values]
    today_used = per_day[-1]
    month_used = sum(per_day)
    month_used_before_today = month_used - today_used
    days_left = (cycle_end - today).days

    daily_allowance: int | None = None
    if monthly_cap > 0:
        remaining = max(monthly_cap - month_used_before_today, 0)
        daily_allowance = remaining // days_left
    if hard_daily > 0:
        daily_allowance = (
            hard_daily if daily_allowance is None else min(daily_allowance, hard_daily)
        )

    exhausted = False
    if monthly_cap > 0 and month_used >= monthly_cap:
        exhausted = True
    if daily_allowance is not None and today_used >= daily_allowance:
        exhausted = True
    return {
        "date": today_key,
        "cycle_start": cycle_start.isoformat(),
        "cycle_end": cycle_end.isoformat(),
        "monthly_cap": monthly_cap or None,
        "month_used": month_used,
        "today_used": today_used,
        "daily_allowance": daily_allowance,
        "days_left": days_left,
        "exhausted": exhausted,
    }


def daily_budget_exhausted_sync() -> bool:
    """True when today's paid fetches hit the budget-derived allowance.

    Spend guard for the proxy-mode shops (2026-09-19: the www-host fix put
    ~550k proxy_render listings onto the paid backend for real). Fail-open
    on Redis trouble — the RPS limiter's local fallback already throttles
    to 1 req/s per process, and accounting must never fail a fetch.
    """
    if proxy_provider_monthly_cap() <= 0 and proxy_provider_daily_cap() <= 0:
        return False
    try:
        return bool(budget_status_sync()["exhausted"])
    except Exception:  # noqa: BLE001 - see docstring
        return False


def read_usage_days_sync(days: int = 14) -> dict[str, int]:
    """{YYYYMMDD: granted tokens} for the last `days` days (missing = 0)."""
    client = _get_redis()
    out: dict[str, int] = {}
    now = time.time()
    keys = [
        time.strftime("%Y%m%d", time.gmtime(now - offset * 86400))
        for offset in range(days)
    ]
    values = client.mget([PROXY_USAGE_KEY_PREFIX + day for day in keys])
    for day, value in zip(keys, values):
        out[day] = int(value) if value else 0
    return out


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
            await asyncio.to_thread(_record_usage_sync)
            return True
        wait_sec = 1.0 / proxy_provider_max_rps()
        if remaining is not None and wait_sec > remaining:
            return False
        await asyncio.sleep(wait_sec)
        if _deadline_remaining(deadline_monotonic) is not None:
            if _deadline_remaining(deadline_monotonic) <= 0:
                return False
        acquired = await asyncio.to_thread(_redis_acquire_sync)
        if acquired:
            await asyncio.to_thread(_record_usage_sync)
        return acquired
    except Exception:
        return await _acquire_local_fallback(deadline_monotonic)


def reset_limiter_state_for_tests() -> None:
    """Clear module-level Redis handle and local fallback clock (tests only)."""
    global _redis_client, _local_fallback_last_monotonic
    _redis_client = None
    _local_fallback_last_monotonic = 0.0
