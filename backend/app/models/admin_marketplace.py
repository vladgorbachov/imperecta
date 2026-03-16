"""AdminMarketplace model for custom marketplaces added via admin UI."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class AdminMarketplace(Base):
    """Marketplace added through admin panel (supplements built-in registry)."""

    __tablename__ = "admin_marketplaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    marketplace_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="XX")
    region: Mapped[str] = mapped_column(String(20), nullable=False, default="other")
    currency: Mapped[str] = mapped_column(String(5), nullable=False, default="USD")
    scraper_type: Mapped[str] = mapped_column(String(50), nullable=False, default="generic")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_scrape_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_scrape_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_scrapes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    successful_scrapes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_scrapes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Product pool quota (recalculated: 50000 / active_marketplace_count)
    product_quota: Mapped[int] = mapped_column(Integer, default=0)
    products_in_pool: Mapped[int] = mapped_column(Integer, default=0)

    # Custom CSS selectors (optional, admin fills via UI if auto-detection fails)
    custom_product_link_selector: Mapped[str | None] = mapped_column(String(500), nullable=True)
    custom_price_selector: Mapped[str | None] = mapped_column(String(500), nullable=True)
    custom_title_selector: Mapped[str | None] = mapped_column(String(500), nullable=True)
    custom_image_selector: Mapped[str | None] = mapped_column(String(500), nullable=True)
    custom_next_page_selector: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Discovery settings
    requires_js: Mapped[bool] = mapped_column(Boolean, default=False)
    rate_limit_delay: Mapped[float] = mapped_column(Float, default=2.0)
    max_concurrent_requests: Mapped[int] = mapped_column(Integer, default=3)
    last_discovery_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
