"""Pydantic schemas for the news module API."""

from datetime import datetime

from pydantic import BaseModel, Field


class NewsItem(BaseModel):
    """Single headline card — no full article body."""

    title: str
    source: str
    published_at: datetime
    snippet: str
    url: str
    image_url: str | None = None


class NewsResponse(BaseModel):
    """Aggregated feed from the provider chain."""

    items: list[NewsItem]
    source_provider: str = Field(
        default="",
        description='Provider id: "newsdata", "currents", "gdelt", or "" when none',
    )
