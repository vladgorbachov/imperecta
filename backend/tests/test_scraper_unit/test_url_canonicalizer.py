"""Pure-logic tests for discovery url_canonicalizer (no DB/network)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from bs4 import BeautifulSoup

from app.models.facts import FactListing
from app.modules.discovery import url_canonicalizer


def test_canonical_from_soup_returns_absolute_without_query_or_fragment() -> None:
    soup = BeautifulSoup(
        '<html><head><link rel="canonical" href="/p/1?x=1#frag"></head></html>',
        "html.parser",
    )
    canonical = url_canonicalizer.canonical_from_soup(
        soup,
        "https://shop.example/cat/",
    )
    assert canonical == "https://shop.example/p/1"


def test_canonical_from_soup_returns_none_without_link() -> None:
    soup = BeautifulSoup("<html><head></head></html>", "html.parser")
    assert url_canonicalizer.canonical_from_soup(soup, "https://shop.example/") is None


def test_canonical_from_soup_rejects_non_http_scheme() -> None:
    soup = BeautifulSoup(
        '<html><head><link rel="canonical" href="mailto:a@b.c"></head></html>',
        "html.parser",
    )
    assert url_canonicalizer.canonical_from_soup(soup, "https://shop.example/") is None


def test_url_hash_matches_fact_listing_compute_url_hash() -> None:
    url = "https://Shop.Example/PATH/?q=1"
    assert url_canonicalizer.url_hash(url) == FactListing.compute_url_hash(url)
    assert url_canonicalizer.url_hash(url) == url_canonicalizer.url_hash(
        "https://shop.example/path/?q=1"
    )


def test_pool_url_prefers_canonical_else_raw() -> None:
    assert url_canonicalizer.pool_url("https://shop.example/p/1", "https://shop.example/raw") == (
        "https://shop.example/p/1"
    )
    assert url_canonicalizer.pool_url(None, "https://shop.example/raw") == "https://shop.example/raw"


@pytest.mark.asyncio
async def test_load_existing_url_hashes_global_in_select() -> None:
    known_hash = url_canonicalizer.url_hash("https://shop.example/p/1")
    other_hash = url_canonicalizer.url_hash("https://shop.example/p/2")
    result = MagicMock()
    result.all.return_value = [(known_hash,)]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    loaded = await url_canonicalizer.load_existing_url_hashes(
        db,
        [known_hash, other_hash],
    )

    assert loaded == {known_hash}
    db.execute.assert_awaited_once()
    stmt = db.execute.await_args.args[0]
    compiled = str(stmt)
    assert "fact_listing.url_hash" in compiled.lower() or "url_hash" in compiled.lower()
    assert "marketplace_id" not in compiled.lower()


@pytest.mark.asyncio
async def test_load_existing_url_hashes_empty_input_skips_query() -> None:
    db = AsyncMock()
    loaded = await url_canonicalizer.load_existing_url_hashes(db, [])
    assert loaded == set()
    db.execute.assert_not_awaited()


def test_phase_style_within_batch_dedup_uses_url_hash_from_submodule() -> None:
    """Mirrors _products_from_results: decision in phase, hash from url_canonicalizer."""
    pool_url = "https://shop.example/product-a"
    results = [
        ("https://shop.example/product-a", "product", pool_url),
        ("https://shop.example/product-a-dup", "product", pool_url),
    ]
    seen_hashes: set[str] = set()
    accepted: list[str] = []
    for _source_url, role, resolved_pool_url in results:
        if role != "product":
            continue
        listing_hash = url_canonicalizer.url_hash(resolved_pool_url)
        if listing_hash in seen_hashes:
            continue
        seen_hashes.add(listing_hash)
        accepted.append(resolved_pool_url)

    assert accepted == [pool_url]
