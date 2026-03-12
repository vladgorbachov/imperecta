"""Markets refresh metadata: audit log for 2-hour scheduled snapshots."""

import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


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
