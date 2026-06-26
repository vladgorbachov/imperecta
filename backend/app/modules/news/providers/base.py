"""Shared news provider contract and relevance constants."""

from __future__ import annotations

from typing import Protocol

from app.modules.news.schemas import NewsItem

RETAIL_KEYWORDS = (
    "retail OR e-commerce OR marketplace OR prices OR consumer goods"
)
SNIPPET_MAX_LENGTH = 240

PROVIDER_NEWSDATA = "newsdata"
PROVIDER_CURRENTS = "currents"
PROVIDER_GDELT = "gdelt"


def truncate_snippet(text: str, *, max_length: int = SNIPPET_MAX_LENGTH) -> str:
    """Trim snippet to copyright-safe length without breaking mid-word when possible."""
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= max_length:
        return cleaned
    truncated = cleaned[: max_length - 1].rsplit(" ", 1)[0]
    return f"{truncated}…" if truncated else f"{cleaned[: max_length - 1]}…"


class NewsProvider(Protocol):
    """External news source; returns normalized items or empty list on failure."""

    @property
    def provider_source(self) -> str:
        """Stable provider id (newsdata, currents, gdelt)."""
        ...

    async def fetch(
        self,
        *,
        country_code: str | None,
        language: str,
    ) -> list[NewsItem]:
        """Fetch headlines for optional country scope and language."""
        ...
