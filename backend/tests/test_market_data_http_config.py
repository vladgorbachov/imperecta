"""Unit tests for market_data HTTP timeout/retry configuration."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.modules.market_data.http_config import (
    is_transient_http_error,
    with_transient_retries,
)


def test_is_transient_http_error_classifies_timeout_and_5xx() -> None:
    assert is_transient_http_error(httpx.TimeoutException("slow"))
    assert is_transient_http_error(httpx.ConnectError("conn"))
    response_500 = MagicMock(status_code=500)
    assert is_transient_http_error(httpx.HTTPStatusError("err", request=MagicMock(), response=response_500))
    response_404 = MagicMock(status_code=404)
    assert not is_transient_http_error(
        httpx.HTTPStatusError("err", request=MagicMock(), response=response_404)
    )
    assert not is_transient_http_error(ValueError("parse"))


@pytest.mark.asyncio
async def test_with_transient_retries_zero_attempts_runs_once() -> None:
  fn = AsyncMock(side_effect=httpx.TimeoutException("slow"))
  with pytest.raises(httpx.TimeoutException):
    await with_transient_retries(fn, retry_attempts=0, label="test")
  assert fn.await_count == 1


@pytest.mark.asyncio
async def test_with_transient_retries_retries_transient_then_succeeds() -> None:
  fn = AsyncMock(
    side_effect=[
      httpx.TimeoutException("slow"),
      {"ok": True},
    ]
  )
  result = await with_transient_retries(fn, retry_attempts=1, label="test")
  assert result == {"ok": True}
  assert fn.await_count == 2


@pytest.mark.asyncio
async def test_with_transient_retries_does_not_retry_4xx() -> None:
  response_404 = MagicMock(status_code=404)
  fn = AsyncMock(
    side_effect=httpx.HTTPStatusError("missing", request=MagicMock(), response=response_404)
  )
  with pytest.raises(httpx.HTTPStatusError):
    await with_transient_retries(fn, retry_attempts=3, label="test")
  assert fn.await_count == 1
