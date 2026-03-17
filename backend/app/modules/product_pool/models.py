"""Global marketplace product pool. NOT user-specific."""

import hashlib
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class GlobalProduct(Base):
    __tablename__ = "global_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    marketplace_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("admin_marketplaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    title: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    original_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    price_change_pct_24h: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    price_change_pct_7d: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    price_change_pct_30d: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    volatility_30d: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scrape_error_count: Mapped[int] = mapped_column(Integer, default=0)
    last_scraper_layer: Mapped[str | None] = mapped_column(String(50), nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    marketplace = relationship("AdminMarketplace", backref="global_products")
    price_snapshots = relationship(
        "GlobalPriceSnapshot",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_global_products_marketplace_status", "marketplace_id", "status"),
        Index("ix_global_products_stale", "status", "last_scraped_at"),
        Index("ix_global_products_gainers", "price_change_pct_24h"),
        Index("ix_global_products_volatile", "volatility_30d"),
        Index("ix_global_products_recent", "discovered_at"),
    )

    @staticmethod
    def compute_url_hash(url: str) -> str:
        """SHA256 hash for URL deduplication."""
        return hashlib.sha256(url.strip().lower().encode()).hexdigest()


class GlobalPriceSnapshot(Base):
    __tablename__ = "global_price_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    global_product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("global_products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    original_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    scraper_layer: Mapped[str | None] = mapped_column(String(50), nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    product = relationship("GlobalProduct", back_populates="price_snapshots")

    __table_args__ = (
        Index("ix_global_snapshots_product_time", "global_product_id", "scraped_at"),
    )
