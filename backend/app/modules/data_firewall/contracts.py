"""Declarative per-column contracts for fact tables (structure only in 1.1)."""

from __future__ import annotations

from typing import Any, TypedDict

from sqlalchemy import Boolean, Column, Date, DateTime, Integer, Numeric, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

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
    FactStock,
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
    "fact_listing": build_table_contract(FactListing),
    "fact_price": build_table_contract(FactPrice),
    "fact_review": build_table_contract(FactReview),
    "fact_stock": build_table_contract(FactStock),
    "fact_promo": build_table_contract(FactPromo),
    "fact_search_trend": build_table_contract(FactSearchTrend),
    "fact_currency_rate": build_table_contract(FactCurrencyRate),
    "fact_tariff": build_table_contract(FactTariff),
    "fact_crypto_price": build_table_contract(FactCryptoPrice),
    "fact_commodity_price": build_table_contract(FactCommodityPrice),
    "fact_fuel_price": build_table_contract(FactFuelPrice),
}
