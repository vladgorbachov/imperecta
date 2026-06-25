"""HTTP timeout/retry settings for market_data provider fetches."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

DEFAULT_MARKET_DATA_TIMEOUT_SECONDS = 15.0

T = TypeVar("T")


@dataclass(frozen=True)
class MarketDataHttpConfig:
    """Timeout and per-provider transient-retry policy from Settings."""

    timeout_seconds: float
    retry_attempts: int


def load_market_data_http_config() -> MarketDataHttpConfig:
    """Read market-data HTTP settings once per orchestration entry."""
    settings = Settings()
    timeout = float(settings.market_data_timeout_seconds)
    if timeout <= 0:
        timeout = DEFAULT_MARKET_DATA_TIMEOUT_SECONDS
    retry_attempts = max(0, int(settings.market_data_retry_attempts))
    return MarketDataHttpConfig(
        timeout_seconds=timeout,
        retry_attempts=retry_attempts,
    )


def is_transient_http_error(exc: BaseException) -> bool:
    """True for timeout, connection errors, and HTTP 5xx (not 4xx or parse failures)."""
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(
        exc,
        (
            httpx.ConnectError,
            httpx.ReadError,
            httpx.WriteError,
            httpx.NetworkError,
            httpx.PoolTimeout,
            httpx.RemoteProtocolError,
        ),
    ):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


async def with_transient_retries(
    fetch_fn: Callable[[], Awaitable[T]],
    *,
    retry_attempts: int,
    label: str,
) -> T:
    """Run ``fetch_fn`` with transient retries before provider failover.

    ``retry_attempts`` is the number of *extra* tries after the first attempt
    (0 = single attempt, preserving legacy behavior).
    """
    total_attempts = 1 + max(0, retry_attempts)
    last_exc: BaseException | None = None
    for attempt in range(1, total_attempts + 1):
        try:
            return await fetch_fn()
        except BaseException as exc:
            last_exc = exc
            if not is_transient_http_error(exc) or attempt >= total_attempts:
                raise
            logger.warning(
                "Transient market_data fetch error (%s) attempt %d/%d: %s",
                label,
                attempt,
                total_attempts,
                exc,
            )
            if retry_attempts > 1 and attempt < total_attempts:
                await asyncio.sleep(min(0.5 * attempt, 2.0))
    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"with_transient_retries exhausted without result: {label}")
