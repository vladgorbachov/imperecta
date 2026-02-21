"""CompetitorProduct model."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class CompetitorProduct(Base):
    """Competitor's product linked to user's product."""

    __tablename__ = "competitor_products"
    __table_args__ = (Index("ix_competitor_products_product_id", "product_id"),)

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    product_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    competitor_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("competitors.id", ondelete="CASCADE"),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    last_promo_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    last_in_stock: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    scraper_type: Mapped[str] = mapped_column(
        String(20),
        default="auto",
        nullable=False,
    )
    css_selector_price: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    product: Mapped["Product"] = relationship("Product", back_populates="competitor_products")
    competitor: Mapped["Competitor"] = relationship(
        "Competitor",
        back_populates="competitor_products",
    )
    price_snapshots: Mapped[list["PriceSnapshot"]] = relationship(
        "PriceSnapshot",
        back_populates="competitor_product",
        cascade="all, delete-orphan",
    )
    alert_events: Mapped[list["AlertEvent"]] = relationship(
        "AlertEvent",
        back_populates="competitor_product",
    )
