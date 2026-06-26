"""URL identity helpers for discovery: canonical resolution, hashing, dedup reads."""

from __future__ import annotations

from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import FactListing
from app.modules.scraper.locale_selection import extract_canonical_url


def canonical_from_soup(soup: BeautifulSoup, page_url: str) -> str | None:
    """Return absolute canonical URL from page soup when present."""
    return extract_canonical_url(soup, page_url)


def pool_url(canonical: str | None, raw_url: str) -> str:
    """Resolve the pool identity URL from canonical link or raw fetch URL."""
    return canonical or raw_url


def url_hash(url: str) -> str:
    """Compute the global pool dedup hash for a URL string."""
    return FactListing.compute_url_hash(url)


async def load_existing_url_hashes(
    db: AsyncSession,
    hashes: list[str],
) -> set[str]:
    """Load url_hash values already present in fact_listing (global scope)."""
    if not hashes:
        return set()
    existing_hashes_result = await db.execute(
        select(FactListing.url_hash).where(FactListing.url_hash.in_(hashes)),
    )
    return {row[0] for row in existing_hashes_result.all() if row[0]}
