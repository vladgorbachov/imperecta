"""Alert schemas aligned with v2 alerts / alert_events tables."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

# Matches ck_alerts_alert_type
ALERT_TYPE_PATTERN = (
    r"^(price_drop|price_increase|price_threshold|out_of_stock|back_in_stock|"
    r"new_competitor|competitor_promo|review_drop|review_spike|trend_spike|trend_drop|currency_shift)$"
)
# Matches ck_alerts_channel
CHANNEL_PATTERN = r"^(email|telegram|push|webhook|all)$"


class AlertCreate(BaseModel):
    product_id: UUID | None = None
    listing_id: UUID | None = None
    marketplace_id: UUID | None = None
    category_id: UUID | None = None
    country_code: str | None = Field(None, max_length=2)
    alert_type: str = Field(..., pattern=ALERT_TYPE_PATTERN)
    threshold_pct: float | None = Field(None, ge=0, le=100)
    threshold_value: float | None = None
    channel: str = Field(..., pattern=CHANNEL_PATTERN)
    webhook_url: str | None = None
    cooldown_minutes: int = Field(60, ge=1)


class AlertUpdate(BaseModel):
    is_active: bool | None = None
    threshold_pct: float | None = Field(None, ge=0, le=100)
    threshold_value: float | None = None
    channel: str | None = Field(None, pattern=CHANNEL_PATTERN)
    cooldown_minutes: int | None = Field(None, ge=1)


class AlertResponse(BaseModel):
    id: UUID
    user_id: UUID
    product_id: UUID | None
    listing_id: UUID | None
    marketplace_id: UUID | None
    category_id: UUID | None
    country_code: str | None
    alert_type: str
    threshold_pct: float | None
    threshold_value: float | None
    channel: str
    webhook_url: str | None
    cooldown_minutes: int
    last_triggered_at: datetime | None
    trigger_count: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    product_name: str | None = None

    model_config = {"from_attributes": True}


class AlertEventResponse(BaseModel):
    id: int
    alert_id: UUID
    listing_id: UUID | None
    fact_price_id: int | None
    old_value: Decimal | None
    new_value: Decimal | None
    change_pct: Decimal | None
    message: str
    severity: str
    ai_explanation: str | None = None
    ai_recommendation: str | None = None
    ai_recommended_price: Decimal | None = None
    ai_confidence: Decimal | None = None
    sent_via: str | None = None
    delivered_at: datetime | None = None
    read_at: datetime | None = None
    triggered_at: datetime
    product_name: str | None = None
    competitor_name: str | None = None
    old_price: Decimal | None = None
    new_price: Decimal | None = None

    model_config = {"from_attributes": True}


class AlertExplanationResponse(BaseModel):
    explanation: str | None
    recommendation: str | None
    recommended_price: float | None
    severity: str | None = None


class AlertAutoResponseResponse(BaseModel):
    recommended_price: float | None
    reasoning: str
    expected_impact: str
