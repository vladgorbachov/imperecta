"""Alert models."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.modules.core.models import User
    from app.modules.user_products.models import CompetitorProduct, Product


class Alert(Base):
    """User alert configuration."""

    __tablename__ = "alerts"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    threshold_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    channel: Mapped[str] = mapped_column(String(20), default="email", nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    user: Mapped[User] = relationship("User", back_populates="alerts")
    product: Mapped[Product | None] = relationship("Product", back_populates="alerts")
    alert_events: Mapped[list["AlertEvent"]] = relationship("AlertEvent", back_populates="alert", cascade="all, delete-orphan")


class AlertEvent(Base):
    """Alert event record when alert was triggered."""

    __tablename__ = "alert_events"
    __table_args__ = (
        Index("ix_alert_events_triggered", "triggered_at"),
        Index("ix_alert_events_alert_triggered", "alert_id", "triggered_at"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    alert_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False)
    competitor_product_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("competitor_products.id", ondelete="SET NULL"), nullable=True
    )
    old_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    new_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    sent_via: Mapped[str] = mapped_column(String(20), nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ai_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_recommended_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    alert: Mapped[Alert] = relationship("Alert", back_populates="alert_events")
    competitor_product: Mapped[CompetitorProduct | None] = relationship("CompetitorProduct", back_populates="alert_events")
