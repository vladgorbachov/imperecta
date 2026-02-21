"""PriceSnapshot model."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class PriceSnapshot(Base):
    """Price snapshot at a point in time."""

    __tablename__ = "price_snapshots"
    __table_args__ = (
        Index("ix_price_snapshots_competitor_product_id", "competitor_product_id"),
        Index("ix_price_snapshots_scraped_at", "scraped_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    competitor_product_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("competitor_products.id", ondelete="CASCADE"),
        nullable=False,
    )
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    old_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    promo_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    in_stock: Mapped[bool] = mapped_column(default=True, nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    competitor_product: Mapped["CompetitorProduct"] = relationship(
        "CompetitorProduct",
        back_populates="price_snapshots",
    )
