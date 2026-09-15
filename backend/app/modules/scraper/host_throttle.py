"""Per-host politeness throttle for all fetch backends.

Every outbound page fetch passes through ``acquire(url)`` before hitting the
network: requests to the same host are spaced at least ``interval`` seconds
apart, regardless of task-level concurrency. The interval comes from
``dim_marketplace.rate_limit_delay`` when a job registered it via
``set_host_interval``; unknown hosts use the module default.

State is kept per running event loop (Celery tasks each run their own loop),
so asyncio primitives never cross loops.
"""

from __future__ import annotations

import asyncio
import time
import weakref
from urllib.parse import urlparse

DEFAULT_HOST_INTERVAL_SEC = 1.0

# host -> configured minimum interval (process-wide; plain floats are loop-safe)
_host_intervals: dict[str, float] = {}

# loop -> {host: [lock, last_request_monotonic]}
_loop_state: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, dict[str, list]]" = (
    weakref.WeakKeyDictionary()
)


def _host_of(url: str) -> str:
    return (urlparse(url).netloc or "").lower()


def set_host_interval(base_url_or_host: object, interval_sec: object) -> None:
    """Register a marketplace's rate_limit_delay for its host (0/None = default).

    Tolerates arbitrary input (ORM Decimals, missing columns): anything that
    does not parse to a host + positive number leaves the default in place.
    """
    if not isinstance(base_url_or_host, str):
        return
    host = _host_of(base_url_or_host) or base_url_or_host.strip().lower()
    if not host:
        return
    try:
        interval = float(interval_sec) if interval_sec is not None else None
    except (TypeError, ValueError):
        interval = None
    if interval is None or interval <= 0:
        _host_intervals.pop(host, None)
    else:
        _host_intervals[host] = interval


def interval_for(host: str) -> float:
    return _host_intervals.get(host, DEFAULT_HOST_INTERVAL_SEC)


async def acquire(url: str) -> None:
    """Wait until this host's minimum request spacing allows the next fetch."""
    host = _host_of(url)
    if not host:
        return
    loop = asyncio.get_running_loop()
    state = _loop_state.get(loop)
    if state is None:
        state = {}
        _loop_state[loop] = state
    entry = state.get(host)
    if entry is None:
        entry = [asyncio.Lock(), 0.0]
        state[host] = entry
    lock, _ = entry
    async with lock:
        interval = interval_for(host)
        now = time.monotonic()
        wait = entry[1] + interval - now
        if wait > 0:
            await asyncio.sleep(wait)
        entry[1] = time.monotonic()
