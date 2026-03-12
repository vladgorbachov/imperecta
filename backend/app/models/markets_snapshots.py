"""Markets snapshot tables: forex, crypto, commodities, ticker. Refreshed every 2 hours."""

from datetime import datetime
from decimal import Decimal
from sqlalchemy import BigInteger, DateTime, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class MarketsForex(Base):
    """Forex pair snapshot. One row per symbol, overwritten on refresh."""

    __tablename__ = "markets_forex"
    __table_args__ = (Index("ix_markets_forex_symbol", "symbol", unique=True),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    bid: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    ask: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    spread: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    change_24h: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    refreshed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class MarketsCrypto(Base):
    """Crypto asset snapshot. One row per symbol."""

    __tablename__ = "markets_crypto"
    __table_args__ = (Index("ix_markets_crypto_symbol", "symbol", unique=True),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    change_24h: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    market_cap: Mapped[Decimal | None] = mapped_column(Numeric(24, 2), nullable=True)
    refreshed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class MarketsCommodity(Base):
    """Commodity/resource snapshot. One row per symbol."""

    __tablename__ = "markets_commodities"
    __table_args__ = (Index("ix_markets_commodities_symbol", "symbol", unique=True),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    change_24h: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    refreshed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class MarketsTickerItem(Base):
    """Ticker bar item. Scrollable strip of symbols with price and change."""

    __tablename__ = "markets_ticker"
    __table_args__ = (Index("ix_markets_ticker_symbol", "symbol", unique=True),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(24, 4), nullable=False)
    change_24h: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(5), nullable=True)
    refreshed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
