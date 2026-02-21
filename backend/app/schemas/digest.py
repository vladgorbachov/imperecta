"""Digest schemas."""

from datetime import datetime
from pydantic import BaseModel


class DigestResponse(BaseModel):
    """Schema for digest response."""

    id: int
    period: str
    content: str | None
    generated_at: datetime

    class Config:
        from_attributes = True
