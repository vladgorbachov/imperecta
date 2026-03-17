"""Alert schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class AlertCreate(BaseModel):
    product_id: UUID | None = None
    type: str = Field(..., pattern="^(price_drop|price_increase|out_of_stock|new_promo)$")
    threshold_percent: float | None = Field(None, ge=0, le=100)
    channel: str = Field(..., pattern="^(email|telegram|both)$")


class AlertUpdate(BaseModel):
    is_active: bool | None = None


class AlertResponse(BaseModel):
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
    id: int
    alert_id: UUID
    product_name: str | None = None
    competitor_name: str | None = None
    old_price: Decimal | None
    new_price: Decimal | None
    message: str
    sent_via: str
    triggered_at: datetime
    severity: str | None = None
    ai_explanation: str | None = None
    ai_recommendation: str | None = None
    ai_recommended_price: Decimal | None = None

    class Config:
        from_attributes = True


class AlertExplanationResponse(BaseModel):
    explanation: str | None
    recommendation: str | None
    recommended_price: float | None
    severity: str | None = None


class AlertAutoResponseResponse(BaseModel):
    recommended_price: float | None
    reasoning: str
    expected_impact: str
