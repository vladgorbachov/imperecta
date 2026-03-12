"""Market Overview tabbed table data. Product/marketplace rows with price changes."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, Index, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class MarketsOverviewItem(Base):
    """Single row for Market Overview tabbed table. Refreshed every 2 hours."""

    __tablename__ = "markets_overview"
    __table_args__ = (
        Index("ix_markets_overview_marketplace", "marketplace"),
        Index("ix_markets_overview_refreshed", "refreshed_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    marketplace: Mapped[str] = mapped_column(String(50), nullable=False)
    marketplace_domain: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    product_name: Mapped[str] = mapped_column(String(500), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(5), default="RUB", nullable=False)
    change_24h: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    change_3d: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    change_1w: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    change_1m: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    sparkline_data: Mapped[list[float]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    refreshed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
