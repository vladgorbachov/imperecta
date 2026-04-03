"""Application tables: alerts, digests, chat, scraping jobs, logs, exports (v2)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from app.models.core import User

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class Alert(Base):
    """User-defined alert rule."""

    __tablename__ = "alerts"

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
    product_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("dim_product.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    listing_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("fact_listing.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    marketplace_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("dim_marketplace.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    category_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("dim_category.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    country_code: Mapped[str | None] = mapped_column(
        String(2),
        ForeignKey("dim_country.country_code", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    alert_type: Mapped[str] = mapped_column(String(30), nullable=False)
    threshold_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    threshold_value: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    channel: Mapped[str] = mapped_column(String(20), default="email", nullable=False)
    webhook_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trigger_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
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

    user: Mapped[User] = relationship("User", back_populates="alerts")
    events: Mapped[list[AlertEvent]] = relationship(
        "AlertEvent",
        back_populates="alert",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "alert_type IN ("
            "'price_drop','price_increase','price_threshold',"
            "'out_of_stock','back_in_stock',"
            "'new_competitor','competitor_promo',"
            "'review_drop','review_spike',"
            "'trend_spike','trend_drop',"
            "'currency_shift'"
            ")",
            name="ck_alerts_alert_type",
        ),
        CheckConstraint(
            "channel IN ('email','telegram','push','webhook','all')",
            name="ck_alerts_channel",
        ),
        Index("idx_alerts_user", "user_id"),
        Index("idx_alerts_active", "is_active", postgresql_where=text("is_active = true")),
        Index("idx_alerts_type", "alert_type"),
    )


class AlertEvent(Base):
    """Alert firing log."""

    __tablename__ = "alert_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    alert_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("alerts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    listing_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("fact_listing.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    fact_price_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    old_value: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    new_value: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    change_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(10), default="medium", nullable=False)
    ai_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_recommended_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    ai_confidence: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    sent_via: Mapped[str | None] = mapped_column(String(20), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    alert: Mapped[Alert] = relationship("Alert", back_populates="events")

    __table_args__ = (
        CheckConstraint(
            "severity IN ('low','medium','high','critical')",
            name="ck_alert_events_severity",
        ),
        Index("idx_alert_events_alert", "alert_id"),
        Index("idx_alert_events_triggered", "triggered_at"),
        Index("idx_alert_events_severity", "severity"),
    )


class Digest(Base):
    """Scheduled or on-demand digest content."""

    __tablename__ = "digests"

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
    period_type: Mapped[str] = mapped_column(String(10), nullable=False)
    digest_type: Mapped[str] = mapped_column(String(30), default="market_overview", nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    content_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    product_ids: Mapped[list[UUID] | None] = mapped_column(ARRAY(PG_UUID(as_uuid=True)), nullable=True)
    marketplace_ids: Mapped[list[UUID] | None] = mapped_column(ARRAY(PG_UUID(as_uuid=True)), nullable=True)
    country_codes: Mapped[list[str] | None] = mapped_column(ARRAY(String(2)), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_via: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    generation_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship("User", back_populates="digests")

    __table_args__ = (
        CheckConstraint(
            "period_type IN ('daily','weekly','monthly','custom')",
            name="ck_digests_period_type",
        ),
        CheckConstraint(
            "digest_type IN ("
            "'market_overview','price_changes','competitor_analysis','trend_report',"
            "'anomaly_digest','custom'"
            ")",
            name="ck_digests_digest_type",
        ),
        Index("idx_digests_user", "user_id"),
        Index("idx_digests_period", "period_start", "period_end"),
        Index("idx_digests_type", "digest_type"),
    )


class AIChatSession(Base):
    """AI analyst chat session."""

    __tablename__ = "ai_chat_sessions"

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
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    context_type: Mapped[str] = mapped_column(String(30), default="general", nullable=False)
    context_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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

    user: Mapped[User] = relationship("User", back_populates="chat_sessions")
    messages: Mapped[list[AIChatMessage]] = relationship(
        "AIChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "context_type IN ("
            "'general','product','marketplace','category','competitor','digest','alert'"
            ")",
            name="ck_ai_chat_sessions_context_type",
        ),
        Index("idx_chat_sessions_user", "user_id"),
        Index("idx_chat_sessions_context", "context_type", "context_id"),
    )


class AIChatMessage(Base):
    """Single message in an AI chat session."""

    __tablename__ = "ai_chat_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tool_calls: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    user_rating: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    session: Mapped[AIChatSession] = relationship("AIChatSession", back_populates="messages")

    __table_args__ = (
        CheckConstraint(
            "role IN ('user','assistant','system','tool')",
            name="ck_ai_chat_messages_role",
        ),
        CheckConstraint(
            "user_rating IS NULL OR (user_rating BETWEEN 1 AND 5)",
            name="ck_ai_chat_messages_user_rating",
        ),
        Index("idx_chat_messages_session", "session_id"),
        Index("idx_chat_messages_created", "created_at"),
    )


class ScrapeJob(Base):
    """Background scrape job definition."""

    __tablename__ = "scrape_jobs"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    job_type: Mapped[str] = mapped_column(String(30), nullable=False)
    marketplace_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("dim_marketplace.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_listings: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    successful: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    triggered_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    triggered_by_user: Mapped[User | None] = relationship(
        "User",
        foreign_keys=[triggered_by],
        back_populates="scrape_jobs_triggered",
    )
    logs: Mapped[list[ScrapeLog]] = relationship("ScrapeLog", back_populates="job", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "job_type IN ('scheduled','manual','retry','backfill','discovery')",
            name="ck_scrape_jobs_job_type",
        ),
        CheckConstraint(
            "status IN ('pending','running','completed','failed','cancelled')",
            name="ck_scrape_jobs_status",
        ),
        Index("idx_scrape_jobs_status", "status"),
        Index("idx_scrape_jobs_marketplace", "marketplace_id"),
        Index("idx_scrape_jobs_created", "created_at"),
    )


class ScrapeLog(Base):
    """Single scrape attempt log line."""

    __tablename__ = "scrape_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    scrape_job_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("scrape_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    listing_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("fact_listing.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    marketplace_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("dim_marketplace.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    price_found: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    in_stock_found: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    proxy_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    scraper_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_category: Mapped[str | None] = mapped_column(String(30), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    job: Mapped[ScrapeJob | None] = relationship("ScrapeJob", back_populates="logs")

    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'success','error','timeout','blocked','captcha',"
            "'not_found','price_not_found','parse_error','missing_critical_data',"
            "'technical_error'"
            ")",
            name="ck_scrape_logs_status",
        ),
        Index("idx_scrape_logs_job", "scrape_job_id"),
        Index("idx_scrape_logs_listing", "listing_id"),
        Index("idx_scrape_logs_status", "status"),
        Index("idx_scrape_logs_created", "created_at"),
    )


class ApiLog(Base):
    """External API call audit log."""

    __tablename__ = "api_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    service: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    endpoint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    method: Mapped[str] = mapped_column(String(10), default="GET", nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('success','error','timeout','rate_limited')",
            name="ck_api_logs_status",
        ),
        Index("idx_api_logs_service", "service"),
        Index("idx_api_logs_status", "status"),
        Index("idx_api_logs_created", "created_at"),
        Index(
            "idx_api_logs_user",
            "user_id",
            postgresql_where=text("user_id IS NOT NULL"),
        ),
    )


class DataExport(Base):
    """User-requested data export job."""

    __tablename__ = "data_exports"

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
    export_type: Mapped[str] = mapped_column(String(30), nullable=False)
    tables_included: Mapped[list[str]] = mapped_column(ARRAY(String(50)), nullable=False)
    filters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    file_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship("User", back_populates="data_exports")

    __table_args__ = (
        CheckConstraint(
            "export_type IN ("
            "'csv','xlsx','json','parquet','pdf_report','powerbi_dataset','api_bulk'"
            ")",
            name="ck_data_exports_export_type",
        ),
        CheckConstraint(
            "status IN ('pending','generating','ready','downloaded','expired','error')",
            name="ck_data_exports_status",
        ),
        Index("idx_exports_user", "user_id"),
        Index("idx_exports_status", "status"),
    )
