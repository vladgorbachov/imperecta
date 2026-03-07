"""ScrapeLog model for logging each scraper run."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class ScrapeLog(Base):
    """Log entry for each scraper execution."""

    __tablename__ = "scrape_logs"
    __table_args__ = (
        Index("ix_scrape_logs_marketplace_created", "marketplace_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    marketplace_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    marketplace_name: Mapped[str] = mapped_column(String(100), nullable=False)
    competitor_product_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("competitor_products.id", ondelete="SET NULL"),
        nullable=True,
    )
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_found: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    proxy_used: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
        nullable=False,
    )
