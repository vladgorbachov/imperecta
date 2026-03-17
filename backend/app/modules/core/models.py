"""Core shared models."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.modules.alerts.models import Alert
    from app.modules.digests.models import Digest
    from app.modules.market_data.models import MarketsPreferences
    from app.modules.user_products.models import Competitor, Product


class UserPlan(enum.Enum):
    """User subscription plan."""

    trial = "trial"
    starter = "starter"
    business = "business"
    pro = "pro"


class User(Base):
    """User account model."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    plan: Mapped[UserPlan] = mapped_column(Enum(UserPlan), default=UserPlan.trial, nullable=False)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, unique=True)
    telegram_link_code: Mapped[str | None] = mapped_column(String(6), nullable=True)
    language: Mapped[str] = mapped_column(String(5), default="en", nullable=False)
    ai_tone: Mapped[str] = mapped_column(String(20), default="balanced", nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    force_password_change: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    products: Mapped[list[Product]] = relationship("Product", back_populates="user", cascade="all, delete-orphan")
    competitors: Mapped[list[Competitor]] = relationship("Competitor", back_populates="user", cascade="all, delete-orphan")
    alerts: Mapped[list[Alert]] = relationship("Alert", back_populates="user", cascade="all, delete-orphan")
    digests: Mapped[list[Digest]] = relationship("Digest", back_populates="user", cascade="all, delete-orphan")
    markets_preferences: Mapped[MarketsPreferences | None] = relationship(
        "MarketsPreferences",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )


class ApiLog(Base):
    """Log entry for each external API call."""

    __tablename__ = "api_logs"
    __table_args__ = (Index("ix_api_logs_service_date", "service", "created_at"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    service: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    endpoint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)
