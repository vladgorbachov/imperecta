"""Fact tables (v2 schema)."""

from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class FactListing(Base):
    """Product listing on a marketplace (URL-level identity)."""

    __tablename__ = "fact_listing"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    product_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("dim_product.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    marketplace_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("dim_marketplace.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seller_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("dim_seller.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    external_url: Mapped[str] = mapped_column(Text, nullable=False)
    # SHA256 of normalized URL for deduplication during discovery.
    url_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    external_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    last_price_eur: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    last_original_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    last_currency_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    last_in_stock: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    last_rating: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    last_review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scraper_type: Mapped[str] = mapped_column(String(30), default="web_api", nullable=False)
    scraper_config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    scrape_interval_minutes: Mapped[int] = mapped_column(Integer, default=360, nullable=False)
    consecutive_errors: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    last_price_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    prices: Mapped[list[FactPrice]] = relationship("FactPrice", back_populates="listing")
    reviews: Mapped[list[FactReview]] = relationship("FactReview", back_populates="listing")
    stocks: Mapped[list[FactStock]] = relationship("FactStock", back_populates="listing")
    promos: Mapped[list["FactPromo"]] = relationship("FactPromo", back_populates="listing")

    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "marketplace_id",
            "seller_id",
            "external_url",
            name="uq_fact_listing_product_marketplace_seller_url",
        ),
        Index("idx_listing_product", "product_id"),
        Index("idx_listing_marketplace", "marketplace_id"),
        Index("idx_listing_seller", "seller_id"),
        Index("idx_listing_active", "is_active", postgresql_where=text("is_active = true")),
        Index("idx_listing_last_checked", "last_checked_at"),
        Index("idx_listing_url_hash", "url_hash", unique=True),
    )

    @staticmethod
    def compute_url_hash(url: str) -> str:
        """Compute SHA256 hash of normalized URL for deduplication."""
        normalized = url.strip().rstrip("/").lower()
        return hashlib.sha256(normalized.encode()).hexdigest()


class FactPrice(Base):
    """Historical prices (partitioned by date_id in the database)."""

    __tablename__ = "fact_price"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    listing_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("fact_listing.id", ondelete="CASCADE"),
        nullable=False,
    )
    date_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("dim_date.date_id", ondelete="RESTRICT"),
        nullable=False,
        primary_key=True,
    )
    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    original_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    price_eur: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    discount_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    price_change_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    in_stock: Mapped[bool | None] = mapped_column(Boolean, default=True, nullable=True)
    delivery_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivery_cost: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    seller_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    promo_label: Mapped[str | None] = mapped_column(String(300), nullable=True)
    is_promoted: Mapped[bool | None] = mapped_column(Boolean, default=False, nullable=True)
    promo_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    scrape_job_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("scrape_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )

    listing: Mapped[FactListing] = relationship("FactListing", back_populates="prices")

    __table_args__ = (
        Index("idx_fact_price_listing", "listing_id"),
        Index("idx_fact_price_date", "date_id"),
        Index("idx_fact_price_scraped", "scraped_at"),
        Index("idx_fact_price_listing_date", "listing_id", "date_id"),
        {"postgresql_partition_by": "RANGE (date_id)"},
    )


class FactReview(Base):
    """Review aggregates per listing and date."""

    __tablename__ = "fact_review"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    listing_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("fact_listing.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("dim_date.date_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    rating_avg: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rating_1_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rating_2_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rating_3_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rating_4_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rating_5_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sentiment_score: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    sentiment_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_reviews_24h: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    listing: Mapped[FactListing] = relationship("FactListing", back_populates="reviews")

    __table_args__ = (
        Index("idx_fact_review_listing", "listing_id"),
        Index("idx_fact_review_date", "date_id"),
        Index("idx_fact_review_listing_date", "listing_id", "date_id"),
    )


class FactStock(Base):
    """Stock availability facts."""

    __tablename__ = "fact_stock"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    listing_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("fact_listing.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("dim_date.date_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    in_stock: Mapped[bool] = mapped_column(Boolean, nullable=False)
    stock_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stock_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    delivery_days_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivery_days_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivery_cost: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    delivery_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    listing: Mapped[FactListing] = relationship("FactListing", back_populates="stocks")

    __table_args__ = (
        Index("idx_fact_stock_listing", "listing_id"),
        Index("idx_fact_stock_date", "date_id"),
        Index(
            "idx_fact_stock_oos",
            "listing_id",
            "in_stock",
            postgresql_where=text("in_stock = false"),
        ),
    )


class FactSearchTrend(Base):
    """Search trend facts."""

    __tablename__ = "fact_search_trend"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    date_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("dim_date.date_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    country_code: Mapped[str] = mapped_column(
        String(2),
        ForeignKey("dim_country.country_code", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    keyword: Mapped[str] = mapped_column(String(300), nullable=False)
    keyword_normalized: Mapped[str] = mapped_column(String(300), nullable=False)
    trend_index: Mapped[int] = mapped_column(Integer, nullable=False)
    search_volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    category_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("dim_category.id", ondelete="SET NULL"),
        nullable=True,
    )
    related_product_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("dim_product.id", ondelete="SET NULL"),
        nullable=True,
    )
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "source IN ("
            "'google_trends','kaspi_trends','amazon_trends',"
            "'allegro_trends','custom'"
            ")",
            name="ck_fact_search_trend_source",
        ),
        Index(
            "idx_trend_keyword",
            "keyword_normalized",
            postgresql_using="gin",
            postgresql_ops={"keyword_normalized": "gin_trgm_ops"},
        ),
        Index("idx_trend_date", "date_id"),
        Index("idx_trend_country", "country_code"),
        Index("idx_trend_source", "source"),
    )


class FactCurrencyRate(Base):
    """Daily FX rates."""

    __tablename__ = "fact_currency_rate"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    date_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("dim_date.date_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    currency_code: Mapped[str] = mapped_column(
        String(3),
        ForeignKey("dim_currency.currency_code", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    rate_to_eur: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    rate_to_usd: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "source IN ("
            "'ecb','cbr','nbu','nbk','nbb','cbu','nbg','cba','cbar','openexchangerates','custom'"
            ")",
            name="ck_fact_currency_rate_source",
        ),
        UniqueConstraint("date_id", "currency_code", "source", name="uq_fact_currency_rate_date_ccy_source"),
        Index("idx_rate_date", "date_id"),
        Index("idx_rate_currency", "currency_code"),
        Index("idx_rate_date_currency", "date_id", "currency_code"),
    )


class FactTariff(Base):
    """HS tariff facts."""

    __tablename__ = "fact_tariff"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    hs_code: Mapped[str] = mapped_column(String(12), nullable=False)
    origin_country: Mapped[str] = mapped_column(
        String(2),
        ForeignKey("dim_country.country_code", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    destination_country: Mapped[str] = mapped_column(
        String(2),
        ForeignKey("dim_country.country_code", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    duty_pct: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    vat_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    excise_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    trade_agreement: Mapped[str | None] = mapped_column(String(100), nullable=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
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
        Index("idx_tariff_hs", "hs_code"),
        Index("idx_tariff_route", "origin_country", "destination_country"),
        Index("idx_tariff_effective", "effective_from", "effective_to"),
    )


class FactPromo(Base):
    """Promotional campaigns."""

    __tablename__ = "fact_promo"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    listing_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("fact_listing.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    marketplace_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("dim_marketplace.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_date_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("dim_date.date_id", ondelete="RESTRICT"),
        nullable=False,
    )
    end_date_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("dim_date.date_id", ondelete="SET NULL"),
        nullable=True,
    )
    promo_type: Mapped[str] = mapped_column(String(30), nullable=False)
    promo_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    discount_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    discount_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    is_marketplace_wide: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    category_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("dim_category.id", ondelete="SET NULL"),
        nullable=True,
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    listing: Mapped[FactListing | None] = relationship("FactListing", back_populates="promos")

    __table_args__ = (
        CheckConstraint(
            "promo_type IN ("
            "'flash_sale','seasonal','clearance','bundle','coupon','loyalty','marketplace_campaign',"
            "'black_friday','singles_day','new_year','other'"
            ")",
            name="ck_fact_promo_promo_type",
        ),
        Index("idx_promo_marketplace", "marketplace_id"),
        Index("idx_promo_listing", "listing_id"),
        Index("idx_promo_dates", "start_date_id", "end_date_id"),
        Index("idx_promo_type", "promo_type"),
    )


class FactCryptoPrice(Base):
    """Cryptocurrency market data. Source: Binance primary, CoinGecko backup."""

    __tablename__ = "fact_crypto_price"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    date_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("dim_date.date_id", ondelete="RESTRICT"),
        nullable=False,
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    price_usd: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    price_eur: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    market_cap_usd: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    volume_24h_usd: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    change_1h_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    change_24h_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    change_7d_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    high_24h_usd: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    low_24h_usd: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    circulating_supply: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    total_supply: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    rank: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "source IN ('binance','coingecko','coinmarketcap','custom')",
            name="ck_crypto_source",
        ),
        UniqueConstraint("date_id", "symbol", "source", name="uq_crypto_date_symbol_source"),
        Index("idx_crypto_date", "date_id"),
        Index("idx_crypto_symbol", "symbol"),
        Index("idx_crypto_date_symbol", "date_id", "symbol"),
    )


class FactCommodityPrice(Base):
    """Commodity prices: metals (GoldAPI) + energy (Alpha Vantage)."""

    __tablename__ = "fact_commodity_price"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    date_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("dim_date.date_id", ondelete="RESTRICT"),
        nullable=False,
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    commodity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    price_usd: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    price_eur: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    change_24h_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    change_7d_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "commodity_type IN ('metal','energy','agricultural')",
            name="ck_commodity_type",
        ),
        CheckConstraint(
            "source IN ('goldapi','alpha_vantage','eia','custom')",
            name="ck_commodity_source",
        ),
        UniqueConstraint("date_id", "symbol", "source", name="uq_commodity_date_symbol_source"),
        Index("idx_commodity_date", "date_id"),
        Index("idx_commodity_symbol", "symbol"),
        Index("idx_commodity_date_symbol", "date_id", "symbol"),
    )


class FactFuelPrice(Base):
    """Retail fuel prices by country. Updated daily."""

    __tablename__ = "fact_fuel_price"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    date_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("dim_date.date_id", ondelete="RESTRICT"),
        nullable=False,
    )
    country_code: Mapped[str] = mapped_column(
        String(2),
        ForeignKey("dim_country.country_code", ondelete="RESTRICT"),
        nullable=False,
    )
    fuel_type: Mapped[str] = mapped_column(String(20), nullable=False)
    price_local: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    currency_code: Mapped[str] = mapped_column(
        String(3),
        ForeignKey("dim_currency.currency_code", ondelete="RESTRICT"),
        nullable=False,
    )
    price_eur: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    change_week_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    change_month_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "fuel_type IN ("
            "'gasoline_92','gasoline_95','gasoline_98','gasoline_100',"
            "'diesel','diesel_premium','lpg','cng','electricity'"
            ")",
            name="ck_fuel_type",
        ),
        UniqueConstraint(
            "date_id",
            "country_code",
            "fuel_type",
            "source",
            name="uq_fuel_date_country_type_source",
        ),
        Index("idx_fuel_date", "date_id"),
        Index("idx_fuel_country", "country_code"),
        Index("idx_fuel_date_country_type", "date_id", "country_code", "fuel_type"),
    )
