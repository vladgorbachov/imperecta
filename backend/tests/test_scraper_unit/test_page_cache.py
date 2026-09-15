"""page_cache bridge: compressed round-trip, single-consumer delete, size cap."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.modules.scraper import page_cache


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}

    def setex(self, key: str, ttl: int, value: bytes) -> None:
        assert ttl == page_cache.PAGE_CACHE_TTL_SEC
        self.store[key] = value

    def get(self, key: str) -> bytes | None:
        return self.store.get(key)

    def delete(self, key: str) -> None:
        self.store.pop(key, None)


def test_put_get_round_trip_and_single_consumer_delete() -> None:
    fake = _FakeRedis()
    with patch.object(page_cache, "_get_redis", return_value=fake):
        url = "https://shop.example/products/scrub"
        html = "<html><body>" + "x" * 5000 + "</body></html>"
        page_cache.put_html(url, html)
        assert len(fake.store) == 1
        assert page_cache.get_html(url) == html
        # hit consumed the key — second read is a miss
        assert page_cache.get_html(url) is None


def test_oversized_page_not_cached() -> None:
    fake = _FakeRedis()
    with patch.object(page_cache, "_get_redis", return_value=fake):
        import os

        # incompressible payload stays above the compressed-size cap
        html = os.urandom(400_000).hex()
        page_cache.put_html("https://shop.example/p", html)
        assert fake.store == {}


def test_redis_failure_degrades_to_miss() -> None:
    broken = MagicMock()
    broken.get.side_effect = RuntimeError("down")
    broken.setex.side_effect = RuntimeError("down")
    with patch.object(page_cache, "_get_redis", return_value=broken):
        page_cache.put_html("https://shop.example/p", "<html></html>")
        assert page_cache.get_html("https://shop.example/p") is None


def test_user_agent_stable_per_host() -> None:
    from app.modules.scraper import fetch_backends as fb

    ua1 = fb._user_agent_for("https://shop.example/a")
    ua2 = fb._user_agent_for("https://shop.example/b/c")
    other = fb._user_agent_for("https://another-shop.example/x")
    assert ua1 == ua2
    assert ua1 in fb._USER_AGENT_POOL
    assert other in fb._USER_AGENT_POOL
    headers = fb._request_headers(url="https://shop.example/a")
    assert headers["User-Agent"] == ua1
    assert "Accept" in headers and "Accept-Language" in headers
