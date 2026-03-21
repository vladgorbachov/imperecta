"""Core models: users, subscriptions, and user-saved products."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from app.models.app_tables import AIChatSession, Alert, DataExport, Digest, ScrapeJob
    from app.models.dimensions import DimProduct

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    """Application user account."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    plan: Mapped[str] = mapped_column(String(20), default="trial", nullable=False)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    language: Mapped[str] = mapped_column(String(5), default="en", nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC", nullable=False)
    ai_tone: Mapped[str] = mapped_column(String(20), default="balanced", nullable=False)
    default_currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)

    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    telegram_link_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    telegram_username: Mapped[str | None] = mapped_column(String(100), nullable=True)

    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    force_password_change: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Dashboard preferences (replaces legacy markets_preferences table).
    preferences: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    subscriptions: Mapped[list[UserSubscription]] = relationship(
        "UserSubscription",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    user_products: Mapped[list[UserProduct]] = relationship(
        "UserProduct",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    alerts: Mapped[list[Alert]] = relationship(
        "Alert",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    digests: Mapped[list[Digest]] = relationship(
        "Digest",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    chat_sessions: Mapped[list[AIChatSession]] = relationship(
        "AIChatSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    scrape_jobs_triggered: Mapped[list[ScrapeJob]] = relationship(
        "ScrapeJob",
        back_populates="triggered_by_user",
        foreign_keys="ScrapeJob.triggered_by",
    )
    data_exports: Mapped[list[DataExport]] = relationship(
        "DataExport",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_users_plan", "plan"),
        Index(
            "idx_users_telegram",
            "telegram_chat_id",
            postgresql_where=text("telegram_chat_id IS NOT NULL"),
        ),
        CheckConstraint(
            "plan IN ('trial','starter','business','pro','enterprise')",
            name="ck_users_plan",
        ),
        CheckConstraint(
            "ai_tone IN ('concise','balanced','detailed')",
            name="ck_users_ai_tone",
        ),
    )


class UserSubscription(Base):
    """Subscription history per user (v2 schema)."""

    __tablename__ = "user_subscriptions"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payment_provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency_code: Mapped[str | None] = mapped_column(String(3), default="EUR", nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship("User", back_populates="subscriptions")

    __table_args__ = (
        CheckConstraint(
            "plan IN ('trial','starter','business','pro','enterprise')",
            name="ck_user_subscriptions_plan",
        ),
        CheckConstraint(
            "status IN ('active','cancelled','expired','past_due')",
            name="ck_user_subscriptions_status",
        ),
        Index("idx_user_subs_user", "user_id"),
        Index("idx_user_subs_status", "status"),
    )


class UserProduct(Base):
    """User tracking row for a canonical dim_product."""

    __tablename__ = "user_products"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("dim_product.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    custom_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    custom_sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    cost_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency_code: Mapped[str | None] = mapped_column(String(3), default="EUR", nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship("User", back_populates="user_products")
    product: Mapped[DimProduct] = relationship("DimProduct", back_populates="user_products")

    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_user_products_user_product"),
        Index("idx_user_products_user", "user_id"),
        Index("idx_user_products_product", "product_id"),
    )
