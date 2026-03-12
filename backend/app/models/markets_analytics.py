"""Category/segment and marketplace analytics. Refreshed every 2 hours."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class MarketsCategoryAnalytics(Base):
    """Category/segment analytics snapshot."""

    __tablename__ = "markets_category_analytics"
    __table_args__ = (
        Index("ix_markets_category_id", "category_id"),
        Index("ix_markets_category_refreshed", "refreshed_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    category_id: Mapped[str] = mapped_column(String(100), nullable=False)
    segment: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    refreshed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class MarketsMarketplaceAnalytics(Base):
    """Marketplace-level analytics. Separate from competitor-benchmark domain."""

    __tablename__ = "markets_marketplace_analytics"
    __table_args__ = (
        Index("ix_markets_marketplace_id", "marketplace_id"),
        Index("ix_markets_marketplace_refreshed", "refreshed_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    marketplace_id: Mapped[str] = mapped_column(String(50), nullable=False)
    marketplace_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    refreshed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
