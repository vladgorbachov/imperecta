"""Dimensional model tables (star schema, v2)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from app.models.core import UserProduct

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class DimDate(Base):
    """Calendar date dimension (YYYYMMDD surrogate key)."""

    __tablename__ = "dim_date"

    date_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    full_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    quarter: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    month_name: Mapped[str] = mapped_column(String(20), nullable=False)
    week_iso: Mapped[int] = mapped_column(Integer, nullable=False)
    day_of_month: Mapped[int] = mapped_column(Integer, nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    day_name: Mapped[str] = mapped_column(String(15), nullable=False)
    is_weekend: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_last_day_of_month: Mapped[bool] = mapped_column(Boolean, nullable=False)
    fiscal_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fiscal_quarter: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_dim_date_full_date", "full_date"),
        CheckConstraint("quarter >= 1 AND quarter <= 4", name="ck_dim_date_quarter"),
        CheckConstraint("month >= 1 AND month <= 12", name="ck_dim_date_month"),
    )


class DimCurrency(Base):
    """Currency reference (ISO 4217)."""

    __tablename__ = "dim_currency"

    currency_code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    symbol: Mapped[str] = mapped_column(String(5), nullable=False)
    decimal_places: Mapped[int | None] = mapped_column(Integer, default=2, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class DimCountry(Base):
    """Country reference (ISO 3166-1 alpha-2)."""

    __tablename__ = "dim_country"

    country_code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    name_local: Mapped[str | None] = mapped_column(String(100), nullable=True)
    region: Mapped[str] = mapped_column(String(30), nullable=False)
    subregion: Mapped[str | None] = mapped_column(String(50), nullable=True)
    currency_code: Mapped[str] = mapped_column(
        String(3),
        ForeignKey("dim_currency.currency_code", ondelete="RESTRICT"),
        nullable=False,
    )
    vat_rate_std: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    vat_rate_reduced: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    ecommerce_market_size_eur: Mapped[int | None] = mapped_column(Integer, nullable=True)
    population: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "region IN ("
            "'CIS','EU','EFTA','Balkans','Caucasus','Central_Asia','Turkey','Other'"
            ")",
            name="ck_dim_country_region",
        ),
    )


class DimMarketplace(Base):
    """Marketplace / price source dimension."""

    __tablename__ = "dim_marketplace"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    marketplace_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    country_code: Mapped[str] = mapped_column(
        String(2),
        ForeignKey("dim_country.country_code", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    operates_in: Mapped[list[str]] = mapped_column(
        ARRAY(String(2)),
        nullable=False,
        server_default=text("ARRAY[]::varchar(2)[]"),
    )
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    api_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    api_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    scraper_type: Mapped[str] = mapped_column(String(30), default="web_api", nullable=False)
    currency_code: Mapped[str] = mapped_column(
        String(3),
        ForeignKey("dim_currency.currency_code", ondelete="RESTRICT"),
        nullable=False,
    )
    locale: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reliability_score: Mapped[float | None] = mapped_column(Numeric(3, 2), default=0.00, nullable=True)
    avg_response_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_scrape_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_scrape_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    monthly_visits: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Discovery & scraping config (admin UI + workers).
    product_quota: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default=text("0"))
    products_in_pool: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default=text("0"))
    requires_js: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default=text("false"))
    # Tiered scrape strategy selector. Maps to the layer-order policy in ScraperPool.
    # 1 — server-rendered shops (Decodo + httpx + Playwright fallback).
    # 2 — modern SPA shops (adds network interception + basic stealth, future).
    # 3 — hostile marketplaces (adds full stealth + sticky residential + LLM fallback, future).
    scrape_tier: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False, server_default=text("1")
    )
    rate_limit_delay: Mapped[float] = mapped_column(
        Numeric(4, 1), default=2.0, nullable=False, server_default=text("2.0")
    )
    custom_product_link_selector: Mapped[str | None] = mapped_column(Text, nullable=True)
    custom_next_page_selector: Mapped[str | None] = mapped_column(Text, nullable=True)
    custom_price_selector: Mapped[str | None] = mapped_column(Text, nullable=True)
    custom_title_selector: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_discovery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_discovery_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_discovery_products_found: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default=text("0")
    )
    discovery_error_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default=text("0")
    )
    discovered_category_urls: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    last_category_recon_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    recon_frontier_state: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, default=None,
    )
    sitemap_url: Mapped[str | None] = mapped_column(
        String(2048), nullable=True, default=None
    )
    last_sitemap_harvest_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    sitemap_resume_offset: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
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

    __table_args__ = (
        CheckConstraint(
            "source_type IN ("
            "'marketplace','price_aggregator','direct_retail','classified',"
            "'b2b_platform','brand_store'"
            ")",
            name="ck_dim_marketplace_source_type",
        ),
        CheckConstraint(
            "scraper_type IN ('web_api','playwright','httpx','api_official','rss','feed')",
            name="ck_dim_marketplace_scraper_type",
        ),
        Index("idx_marketplace_country", "country_code"),
        Index("idx_marketplace_type", "source_type"),
        Index("idx_marketplace_code", "marketplace_code"),
    )


class DimCategory(Base):
    """Hierarchical product category."""

    __tablename__ = "dim_category"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(200), nullable=True)
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    parent_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("dim_category.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    hs_code_prefix: Mapped[str | None] = mapped_column(String(10), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    product_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    parent: Mapped[DimCategory | None] = relationship(
        "DimCategory",
        remote_side="DimCategory.id",
        back_populates="children",
    )
    children: Mapped[list[DimCategory]] = relationship(
        "DimCategory",
        back_populates="parent",
    )
    products: Mapped[list[DimProduct]] = relationship("DimProduct", back_populates="category")

    __table_args__ = (
        Index("idx_category_parent", "parent_id"),
        Index(
            "idx_category_path",
            "path",
            postgresql_using="gin",
            postgresql_ops={"path": "gin_trgm_ops"},
        ),
        Index("idx_category_slug", "slug"),
    )


class DimBrand(Base):
    """Brand dimension."""

    __tablename__ = "dim_brand"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    name_normalized: Mapped[str] = mapped_column(String(200), nullable=False)
    country_code: Mapped[str | None] = mapped_column(
        String(2),
        ForeignKey("dim_country.country_code", ondelete="SET NULL"),
        nullable=True,
    )
    website_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    products: Mapped[list[DimProduct]] = relationship("DimProduct", back_populates="brand")

    __table_args__ = (
        Index("idx_brand_slug", "slug"),
        Index("idx_brand_normalized", "name_normalized", unique=True),
    )


class DimProduct(Base):
    """Canonical product dimension."""

    __tablename__ = "dim_product"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    name_normalized: Mapped[str] = mapped_column(String(500), nullable=False)
    sku_universal: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mpn: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("dim_category.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    brand_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("dim_brand.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_urls: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("ARRAY[]::text[]"),
    )
    hs_code: Mapped[str | None] = mapped_column(String(12), nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
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

    category: Mapped[DimCategory | None] = relationship("DimCategory", back_populates="products")
    brand: Mapped[DimBrand | None] = relationship("DimBrand", back_populates="products")
    user_products: Mapped[list[UserProduct]] = relationship(
        "UserProduct",
        back_populates="product",
    )

    __table_args__ = (
        Index("idx_product_category", "category_id"),
        Index("idx_product_brand", "brand_id"),
        Index(
            "idx_product_name",
            "name_normalized",
            postgresql_using="gin",
            postgresql_ops={"name_normalized": "gin_trgm_ops"},
        ),
        Index(
            "idx_product_sku",
            "sku_universal",
            postgresql_where=text("sku_universal IS NOT NULL"),
        ),
        Index(
            "idx_product_attributes",
            "attributes",
            postgresql_using="gin",
        ),
    )


class DimSeller(Base):
    """Seller / store on a marketplace."""

    __tablename__ = "dim_seller"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    name_normalized: Mapped[str] = mapped_column(String(300), nullable=False)
    marketplace_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("dim_marketplace.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_seller_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    seller_type: Mapped[str] = mapped_column(String(30), default="third_party", nullable=False)
    store_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    rating: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
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

    marketplace: Mapped[DimMarketplace] = relationship(
        "DimMarketplace",
        foreign_keys=[marketplace_id],
    )

    __table_args__ = (
        CheckConstraint(
            "seller_type IN ('first_party','third_party','brand_official','unknown')",
            name="ck_dim_seller_seller_type",
        ),
        Index("idx_seller_marketplace", "marketplace_id"),
        Index("idx_seller_external", "marketplace_id", "external_seller_id"),
        Index(
            "idx_seller_name",
            "name_normalized",
            postgresql_using="gin",
            postgresql_ops={"name_normalized": "gin_trgm_ops"},
        ),
    )
