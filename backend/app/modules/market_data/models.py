"""Market data models."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.modules.core.models import User


class MarketsForex(Base):
    """Forex pair snapshot. One row per symbol, overwritten on refresh."""

    __tablename__ = "markets_forex"
    __table_args__ = (Index("ix_markets_forex_symbol", "symbol", unique=True),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    bid: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    ask: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    spread: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False)
    change_24h: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    refreshed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class MarketsCrypto(Base):
    """Crypto asset snapshot. One row per symbol."""

    __tablename__ = "markets_crypto"
    __table_args__ = (Index("ix_markets_crypto_symbol", "symbol", unique=True),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    change_24h: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    market_cap: Mapped[float | None] = mapped_column(Numeric(24, 2), nullable=True)
    refreshed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class MarketsCommodity(Base):
    """Commodity/resource snapshot. One row per symbol."""

    __tablename__ = "markets_commodities"
    __table_args__ = (Index("ix_markets_commodities_symbol", "symbol", unique=True),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    price: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    change_24h: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    refreshed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class MarketsTickerItem(Base):
    """Ticker bar item. Scrollable strip of symbols with price and change."""

    __tablename__ = "markets_ticker"
    __table_args__ = (Index("ix_markets_ticker_symbol", "symbol", unique=True),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    price: Mapped[float] = mapped_column(Numeric(24, 4), nullable=False)
    change_24h: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(5), nullable=True)
    refreshed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class MarketsPreferences(Base):
    """User preferences for Markets page: country and favorite instruments."""

    __tablename__ = "markets_preferences"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    preferred_country_code: Mapped[str | None] = mapped_column(
        String(3),
        nullable=True,
    )
    favorite_instrument_ids: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
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

    user: Mapped[User] = relationship("User", back_populates="markets_preferences")


class MarketsRefreshType(enum.Enum):
    """Refresh job type."""

    forex = "forex"
    crypto = "crypto"
    commodities = "commodities"
    fuel = "fuel"
    ticker = "ticker"
    overview = "overview"
    category = "category"
    marketplace = "marketplace"
    opportunities = "opportunities"


class MarketsRefreshStatus(enum.Enum):
    """Refresh job status."""

    pending = "pending"
    running = "running"
    success = "success"
    error = "error"


class MarketsRefreshLog(Base):
    """Log entry for each markets data refresh cycle."""

    __tablename__ = "markets_refresh_log"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    refresh_type: Mapped[MarketsRefreshType] = mapped_column(
        Enum(MarketsRefreshType),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[MarketsRefreshStatus] = mapped_column(
        Enum(MarketsRefreshStatus),
        default=MarketsRefreshStatus.pending,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    provider_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country_scope: Mapped[str | None] = mapped_column(String(10), nullable=True)


class MarketsCategoryAnalytics(Base):
    """Category/segment analytics snapshot."""

    __tablename__ = "markets_category_analytics"
    __table_args__ = (
        Index("ix_markets_category_id", "category_id"),
        Index("ix_markets_category_refreshed", "refreshed_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    category_id: Mapped[str] = mapped_column(String(100), nullable=False)
    segment: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MarketsMarketplaceAnalytics(Base):
    """Marketplace-level analytics."""

    __tablename__ = "markets_marketplace_analytics"
    __table_args__ = (
        Index("ix_markets_marketplace_id", "marketplace_id"),
        Index("ix_markets_marketplace_refreshed", "refreshed_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    marketplace_id: Mapped[str] = mapped_column(String(50), nullable=False)
    marketplace_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MarketsOpportunityBlock(Base):
    """Opportunity block: actionable insight with metrics."""

    __tablename__ = "markets_opportunities"
    __table_args__ = (
        Index("ix_markets_opportunities_type", "block_type"),
        Index("ix_markets_opportunities_refreshed", "refreshed_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    block_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
