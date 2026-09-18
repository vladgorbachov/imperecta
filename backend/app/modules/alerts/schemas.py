"""Request/response contracts for user price-alert rules and events (P3)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

AlertType = Literal["price_drop", "price_rise", "availability"]
# in_app: no external delivery — the alert_events row IS the delivery
# (header bell / dashboard stream render it).
AlertChannel = Literal["email", "telegram", "webhook", "in_app"]


class AlertRuleCreate(BaseModel):
    listing_id: UUID | None = None
    product_id: UUID | None = None
    marketplace_id: UUID | None = None
    alert_type: AlertType
    threshold_pct: float | None = Field(default=None, gt=0, le=100)
    channel: AlertChannel = "email"
    # Full enabled set (P15); legacy payloads without it get [channel].
    channels: list[AlertChannel] | None = Field(default=None, min_length=1)
    webhook_url: str | None = None
    cooldown_minutes: int = Field(default=60, ge=0, le=10_080)


class AlertRuleUpdate(BaseModel):
    alert_type: AlertType | None = None
    threshold_pct: float | None = Field(default=None, gt=0, le=100)
    channel: AlertChannel | None = None
    channels: list[AlertChannel] | None = Field(default=None, min_length=1)
    webhook_url: str | None = None
    cooldown_minutes: int | None = Field(default=None, ge=0, le=10_080)
    is_active: bool | None = None


class AlertRule(BaseModel):
    id: UUID
    listing_id: UUID | None = None
    product_id: UUID | None = None
    marketplace_id: UUID | None = None
    alert_type: str
    threshold_pct: float | None = None
    channel: str
    channels: list[str] = Field(default_factory=list)
    webhook_url: str | None = None
    cooldown_minutes: int
    is_active: bool
    last_triggered_at: datetime | None = None
    trigger_count: int
    created_at: datetime | None = None
    product_title: str | None = None
    marketplace_name: str | None = None


class AlertRulesResponse(BaseModel):
    items: list[AlertRule]
    total: int


class AlertEventItem(BaseModel):
    id: int
    rule_id: UUID
    alert_type: str | None = None
    product_title: str | None = None
    marketplace_name: str | None = None
    old_price: float | None = None
    new_price: float | None = None
    currency: str | None = None
    change_pct: float | None = None
    triggered_at: datetime


class AlertEventsResponse(BaseModel):
    items: list[AlertEventItem]
    total: int
    limit: int
    offset: int
