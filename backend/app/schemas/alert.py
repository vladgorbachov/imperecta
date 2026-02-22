"""Alert schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class AlertCreate(BaseModel):
    """Schema for alert creation."""

    product_id: UUID | None = None
    type: str = Field(..., pattern="^(price_drop|price_increase|out_of_stock|new_promo)$")
    threshold_percent: float | None = Field(None, ge=0, le=100)
    channel: str = Field(..., pattern="^(email|telegram|both)$")


class AlertUpdate(BaseModel):
    """Schema for alert update."""

    is_active: bool | None = None


class AlertResponse(BaseModel):
    """Schema for alert response."""

    id: UUID
    product_id: UUID | None
    product_name: str | None = None
    type: str
    threshold_percent: float | None
    channel: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AlertEventResponse(BaseModel):
    """Schema for alert event response."""

    id: int
    alert_id: UUID
    product_name: str | None = None
    competitor_name: str | None = None
    old_price: Decimal | None
    new_price: Decimal | None
    message: str
    sent_via: str
    triggered_at: datetime

    class Config:
        from_attributes = True
