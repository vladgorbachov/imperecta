"""Digest schemas aligned with v2 digests table."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DigestResponse(BaseModel):
    """Response model matching ORM Digest."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    period_type: str
    digest_type: str
    period_start: datetime
    period_end: datetime
    title: str | None = None
    content_md: str | None = None
    summary_json: dict[str, Any] | None = None
    product_ids: list[UUID] | None = None
    marketplace_ids: list[UUID] | None = None
    country_codes: list[str] | None = None
    sent_at: datetime | None = None
    sent_via: str | None = None
    tokens_used: int | None = None
    model_used: str | None = None
    generation_ms: int | None = None
    created_at: datetime
