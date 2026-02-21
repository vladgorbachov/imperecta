"""Alert schemas."""

from pydantic import BaseModel


class AlertCreate(BaseModel):
    """Schema for alert creation."""

    product_id: int | None = None
    threshold_percent: int | None = None
    channel: str


class AlertResponse(BaseModel):
    """Schema for alert response."""

    id: int
    product_id: int | None
    threshold_percent: int | None
    channel: str
    is_active: bool

    class Config:
        from_attributes = True
