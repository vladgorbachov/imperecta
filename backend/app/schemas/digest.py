"""Digest schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DigestResponse(BaseModel):
    """Schema for digest response."""

    id: UUID
    period_type: str
    period_start: datetime
    period_end: datetime
    content_md: str
    sent_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True
