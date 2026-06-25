"""Declarative per-column contracts for fact tables (structure only in 1.1)."""

from __future__ import annotations

from typing import Any, TypedDict

from sqlalchemy import Boolean, Column, Date, DateTime, Integer, Numeric, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from app.models.app_tables import ApiLog, ScrapeJob, ScrapeLog
from app.models.dimensions import DimProduct, DimMarketplace
from app.models.facts import (
    FactCommodityPrice,
    FactCryptoPrice,
    FactCurrencyRate,
    FactFuelPrice,
    FactListing,
    FactPrice,
    FactPromo,
    FactReview,
    FactSearchTrend,
    FactTariff,
)


class ColumnContract(TypedDict, total=False):
    """Per-column contract metadata for firewall enforcement (1.2+)."""

    type: str
    nullable: bool
    max_len: int | None
    precision: int | None
    scale: int | None
    check_values: list[str] | None


def _sql_type_name(column: Column[Any]) -> str:
    col_type = column.type
    if isinstance(col_type, Numeric):
        return "numeric"
    if isinstance(col_type, String):
        return "string"
    if isinstance(col_type, Text):
        return "text"
    if isinstance(col_type, Integer):
        return "integer"
    if isinstance(col_type, SmallInteger):
        return "smallint"
    if isinstance(col_type, Boolean):
        return "boolean"
    if isinstance(col_type, DateTime):
        return "datetime"
    if isinstance(col_type, Date):
        return "date"
    if isinstance(col_type, PG_UUID):
        return "uuid"
    if isinstance(col_type, JSONB):
        return "jsonb"
    return type(col_type).__name__


def _check_values_for_table(model: type, column_name: str) -> list[str] | None:
    for constraint in getattr(model, "__table_args__", ()) or ():
        if not hasattr(constraint, "sqltext"):
            continue
        sqltext = str(constraint.sqltext)
        if column_name not in sqltext.lower():
            continue
        if " IN (" in sqltext.upper():
            inner = sqltext.split(" IN (", 1)[1].rsplit(")", 1)[0]
            values = [
                part.strip().strip("'").strip('"')
                for part in inner.split(",")
                if part.strip()
            ]
            return values or None
    return None


def _contract_from_column(model: type, column: Column[Any]) -> ColumnContract:
    col_type = column.type
    contract: ColumnContract = {
        "type": _sql_type_name(column),
        "nullable": bool(column.nullable),
    }
    if isinstance(col_type, String):
        contract["max_len"] = col_type.length
    if isinstance(col_type, Numeric):
        contract["precision"] = col_type.precision
        contract["scale"] = col_type.scale
    checks = _check_values_for_table(model, column.key)
    if checks:
        contract["check_values"] = checks
    return contract


def build_table_contract(model: type) -> dict[str, ColumnContract]:
    """Build a column-name -> contract map from a SQLAlchemy ORM model."""
    table = model.__table__
    return {
        column.key: _contract_from_column(model, column)
        for column in table.columns
    }


FACT_TABLE_CONTRACTS: dict[str, dict[str, ColumnContract]] = {
    "dim_product": build_table_contract(DimProduct),
    "dim_marketplace": build_table_contract(DimMarketplace),
    "fact_listing": build_table_contract(FactListing),
    "fact_price": build_table_contract(FactPrice),
    "fact_review": build_table_contract(FactReview),
    "fact_promo": build_table_contract(FactPromo),
    "fact_search_trend": build_table_contract(FactSearchTrend),
    "fact_currency_rate": build_table_contract(FactCurrencyRate),
    "fact_tariff": build_table_contract(FactTariff),
    "fact_crypto_price": build_table_contract(FactCryptoPrice),
    "fact_commodity_price": build_table_contract(FactCommodityPrice),
    "fact_fuel_price": build_table_contract(FactFuelPrice),
    "scrape_jobs": build_table_contract(ScrapeJob),
    "scrape_logs": build_table_contract(ScrapeLog),
    "api_logs": build_table_contract(ApiLog),
}

# Per-table natural keys included in the HMAC locator sub-dict (subset of signed fields).
TABLE_LOCATORS: dict[str, tuple[str, ...]] = {
    "fact_price": ("listing_id", "date_id"),
    "fact_listing": ("url_hash",),
    "dim_product": ("id",),
    "dim_marketplace": ("id",),
    "scrape_jobs": ("id",),
    "fact_currency_rate": ("date_id", "currency_code", "source"),
    "fact_crypto_price": ("date_id", "symbol", "source"),
    "fact_commodity_price": ("date_id", "symbol", "source"),
    "scrape_logs": (),
    "api_logs": (),
}


def extract_locator(table: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Return the locator subset from signed fields; raise when a locator column is absent."""
    locator_keys = TABLE_LOCATORS.get(table)
    if locator_keys is None:
        raise ValueError(f"no locator contract for table: {table}")
    locator: dict[str, Any] = {}
    for key in locator_keys:
        if key not in fields:
            raise ValueError(
                f"locator column missing from fields: {key} for table {table}",
            )
        locator[key] = fields[key]
    return locator
