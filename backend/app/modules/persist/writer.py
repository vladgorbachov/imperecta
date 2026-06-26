"""Mutation-free persistence — verify HMAC then write verbatim."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import and_, delete, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.app_tables import ApiLog, ScrapeJob, ScrapeLog
from app.models.dimensions import DimDate, DimMarketplace, DimProduct
from app.models.facts import (
    FactCommodityPrice,
    FactCryptoPrice,
    FactCurrencyRate,
    FactListing,
    FactPrice,
)
from app.modules.data_firewall.contracts import TABLE_LOCATORS, extract_locator
from app.modules.data_firewall.reject_store import write_reject_data
from app.modules.data_firewall.signing import SignedBatch, SignedRecord, verify, verify_batch
from app.observability.sentry_init import capture_exception_if_initialized

logger = logging.getLogger(__name__)
slog = structlog.get_logger(__name__)

SUPPORTED_WRITE_OPERATIONS: dict[str, frozenset[str]] = {
    "dim_date": frozenset({"insert"}),
    "dim_product": frozenset({"insert", "update", "delete"}),
    "dim_marketplace": frozenset({"insert", "update", "delete"}),
    "scrape_jobs": frozenset({"insert", "update", "delete"}),
    "fact_listing": frozenset({"insert", "update", "delete"}),
    "fact_price": frozenset({"insert", "delete"}),
    "fact_currency_rate": frozenset({"insert", "delete"}),
    "fact_crypto_price": frozenset({"insert", "delete"}),
    "fact_commodity_price": frozenset({"insert", "delete"}),
    "scrape_logs": frozenset({"insert"}),
    "api_logs": frozenset({"insert"}),
}

_TABLE_MODELS: dict[str, type] = {
    "dim_date": DimDate,
    "dim_product": DimProduct,
    "dim_marketplace": DimMarketplace,
    "scrape_jobs": ScrapeJob,
    "fact_listing": FactListing,
    "fact_price": FactPrice,
    "fact_currency_rate": FactCurrencyRate,
    "fact_crypto_price": FactCryptoPrice,
    "fact_commodity_price": FactCommodityPrice,
    "scrape_logs": ScrapeLog,
    "api_logs": ApiLog,
}


def _locator_matches_fields(table: str, fields: dict[str, Any], locator: dict[str, Any]) -> bool:
    """Defence in depth: signed locator must match the fields subset."""
    try:
        expected = extract_locator(table, fields)
    except ValueError:
        return False
    return expected == locator


def _verify_signed_record(signed: SignedRecord) -> str | None:
    """Return reject_reason when verification fails; None when the record is valid."""
    if not verify(
        table=signed.table,
        operation=signed.operation,
        fields=signed.fields,
        locator=signed.locator,
        signature=signed.signature,
    ):
        return "invalid_signature"
    if not _locator_matches_fields(signed.table, signed.fields, signed.locator):
        return "locator_mismatch"
    supported = SUPPORTED_WRITE_OPERATIONS.get(signed.table)
    if supported is None or signed.operation not in supported:
        return "unsupported_operation"
    return None


def _verify_signed_batch(signed: SignedBatch) -> str | None:
    """Return reject_reason when batch verification fails; None when valid."""
    if not verify_batch(
        table=signed.table,
        operation=signed.operation,
        rows=signed.rows,
        locator=signed.locator,
        signature=signed.signature,
    ):
        return "invalid_signature"
    if signed.locator:
        for row in signed.rows:
            if not _locator_matches_fields(signed.table, row, signed.locator):
                return "locator_mismatch"
    supported = SUPPORTED_WRITE_OPERATIONS.get(signed.table)
    if supported is None or signed.operation not in supported:
        return "unsupported_operation"
    return None


@dataclass(frozen=True)
class PersistResult:
    """Outcome of a persist write; bool-compatible for insert callers."""

    ok: bool
    rows_affected: int | None = None
    no_target: bool = False

    def __bool__(self) -> bool:
        return self.ok


@dataclass(frozen=True)
class PersistContext:
    """Non-signed routing metadata for reject_data and delete keys."""

    source: str
    marketplace_id: UUID | None = None
    listing_id: UUID | None = None
    date_id: int | None = None


def _parse_uuid(value: Any) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise TypeError(f"unsupported datetime value: {type(value)!r}")


def _orm_fields_for_table(table: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Map signed canonical values to ORM constructor kwargs (no business mutation)."""
    out = dict(fields)
    if "listing_id" in out:
        out["listing_id"] = _parse_uuid(out["listing_id"])
    if "scrape_job_id" in out:
        out["scrape_job_id"] = _parse_uuid(out["scrape_job_id"])
    if "product_id" in out:
        out["product_id"] = _parse_uuid(out["product_id"])
    if "marketplace_id" in out:
        out["marketplace_id"] = _parse_uuid(out["marketplace_id"])
    if "parent_job_id" in out:
        out["parent_job_id"] = _parse_uuid(out["parent_job_id"])
    if "triggered_by" in out:
        out["triggered_by"] = _parse_uuid(out["triggered_by"])
    if "user_id" in out:
        out["user_id"] = _parse_uuid(out["user_id"])
    if "id" in out:
        out["id"] = _parse_uuid(out["id"])
    if "scraped_at" in out:
        out["scraped_at"] = _parse_datetime(out["scraped_at"])
    if "fetched_at" in out:
        out["fetched_at"] = _parse_datetime(out["fetched_at"])
    if "created_at" in out:
        out["created_at"] = _parse_datetime(out["created_at"])
    if "updated_at" in out:
        out["updated_at"] = _parse_datetime(out["updated_at"])
    return out


def _reject_persist(
    db: Session,
    *,
    ctx: PersistContext,
    table: str,
    fields: dict[str, Any],
    reject_reason: str,
    signature_present: bool,
    operation: str = "insert",
) -> PersistResult:
    slog.error(
        "data_firewall_flag_missing",
        table=table,
        source=ctx.source,
        reject_reason=reject_reason,
        signature_present=signature_present,
    )
    try:
        import sentry_sdk

        if sentry_sdk.is_initialized():
            sentry_sdk.capture_message(
                "data_firewall_flag_missing",
                level="error",
                extras={
                    "table": table,
                    "source": ctx.source,
                    "reject_reason": reject_reason,
                },
            )
    except Exception as exc:
        capture_exception_if_initialized(exc)

    write_reject_data(
        db,
        source=ctx.source,
        table_target=table,
        reject_reason=reject_reason,
        raw_payload=fields,
        rejected_by="persist",
        marketplace_id=ctx.marketplace_id,
        listing_id=ctx.listing_id,
        signature_present=signature_present,
        operation=operation,
    )
    return PersistResult(ok=False)


def _model_for_table(table: str) -> type:
    model = _TABLE_MODELS.get(table)
    if model is None:
        raise ValueError(f"unsupported persist table: {table}")
    return model


def _orm_locator(table: str, locator: dict[str, Any]) -> dict[str, Any]:
    return _orm_fields_for_table(table, locator)


def _locator_where(model: type, table: str, orm_locator: dict[str, Any]):
    locator_keys = TABLE_LOCATORS[table]
    clauses = [getattr(model, key) == orm_locator[key] for key in locator_keys]
    if len(clauses) == 1:
        return clauses[0]
    return and_(*clauses)


def _value_fields_minus_locator(table: str, orm_fields: dict[str, Any]) -> dict[str, Any]:
    locator_keys = set(TABLE_LOCATORS[table])
    return {key: value for key, value in orm_fields.items() if key not in locator_keys}


def _persist_result_from_rowcount(rowcount: int) -> PersistResult:
    return PersistResult(
        ok=True,
        rows_affected=rowcount,
        no_target=rowcount == 0,
    )


def _write_sync_update(
    db: Session,
    signed: SignedRecord,
    *,
    ctx: PersistContext,
) -> PersistResult:
    table = signed.table
    model = _model_for_table(table)
    orm_fields = _orm_fields_for_table(table, signed.fields)
    value_fields = _value_fields_minus_locator(table, orm_fields)
    if not value_fields:
        return _reject_persist(
            db,
            ctx=ctx,
            table=table,
            fields=signed.fields,
            reject_reason="nothing_to_update",
            signature_present=bool(signed.signature),
            operation=signed.operation,
        )
    orm_locator = _orm_locator(table, signed.locator)
    result = db.execute(
        update(model)
        .where(_locator_where(model, table, orm_locator))
        .values(**value_fields),
    )
    return _persist_result_from_rowcount(result.rowcount)


def _write_sync_delete(
    db: Session,
    signed: SignedRecord,
) -> PersistResult:
    table = signed.table
    model = _model_for_table(table)
    orm_locator = _orm_locator(table, signed.locator)
    result = db.execute(delete(model).where(_locator_where(model, table, orm_locator)))
    return _persist_result_from_rowcount(result.rowcount)


async def _write_async_delete(
    db: AsyncSession,
    signed: SignedRecord,
) -> PersistResult:
    table = signed.table
    model = _model_for_table(table)
    orm_locator = _orm_locator(table, signed.locator)
    result = await db.execute(delete(model).where(_locator_where(model, table, orm_locator)))
    return _persist_result_from_rowcount(result.rowcount)


def write_sync(
    db: Session,
    signed: SignedRecord | None,
    *,
    ctx: PersistContext,
) -> PersistResult:
    """Verify signature and write verbatim to the target fact table (sync Session)."""
    if signed is None:
        return _reject_persist(
            db,
            ctx=ctx,
            table="unknown",
            fields={},
            reject_reason="missing_signed_record",
            signature_present=False,
            operation="insert",
        )

    reject_reason = _verify_signed_record(signed)
    if reject_reason is not None:
        return _reject_persist(
            db,
            ctx=ctx,
            table=signed.table,
            fields=signed.fields,
            reject_reason=reject_reason,
            signature_present=bool(signed.signature),
            operation=signed.operation,
        )

    operation = signed.operation
    if operation == "update":
        return _write_sync_update(db, signed, ctx=ctx)
    if operation == "delete":
        return _write_sync_delete(db, signed)

    orm_fields = _orm_fields_for_table(signed.table, signed.fields)
    table = signed.table

    if table == "fact_price":
        listing_id = orm_fields["listing_id"]
        date_id = orm_fields["date_id"]
        db.execute(
            delete(FactPrice).where(
                FactPrice.listing_id == listing_id,
                FactPrice.date_id == date_id,
            ),
        )
        db.add(FactPrice(**orm_fields))
        return PersistResult(ok=True, rows_affected=1)

    if table == "dim_product":
        db.add(DimProduct(**orm_fields))
        return PersistResult(ok=True, rows_affected=1)

    if table == "fact_listing":
        db.add(FactListing(**orm_fields))
        return PersistResult(ok=True, rows_affected=1)

    if table == "scrape_jobs":
        db.add(ScrapeJob(**orm_fields))
        return PersistResult(ok=True, rows_affected=1)

    if table == "dim_marketplace":
        db.add(DimMarketplace(**orm_fields))
        return PersistResult(ok=True, rows_affected=1)

    if table == "dim_date":
        full_date = orm_fields.get("full_date")
        if isinstance(full_date, str):
            from datetime import date as date_type

            orm_fields = {**orm_fields, "full_date": date_type.fromisoformat(full_date)}
        stmt = (
            pg_insert(DimDate)
            .values(**orm_fields)
            .on_conflict_do_nothing(index_elements=["date_id"])
        )
        result = db.execute(stmt)
        return _persist_result_from_rowcount(result.rowcount)

    date_id = orm_fields["date_id"]

    if table == "fact_currency_rate":
        db.execute(
            delete(FactCurrencyRate).where(
                FactCurrencyRate.date_id == date_id,
                FactCurrencyRate.currency_code == orm_fields["currency_code"],
                FactCurrencyRate.source == orm_fields["source"],
            ),
        )
        db.add(FactCurrencyRate(**orm_fields))
        return PersistResult(ok=True, rows_affected=1)

    if table == "fact_crypto_price":
        db.execute(
            delete(FactCryptoPrice).where(
                FactCryptoPrice.date_id == date_id,
                FactCryptoPrice.symbol == orm_fields["symbol"],
                FactCryptoPrice.source == orm_fields["source"],
            ),
        )
        db.add(FactCryptoPrice(**orm_fields))
        return PersistResult(ok=True, rows_affected=1)

    if table == "fact_commodity_price":
        db.execute(
            delete(FactCommodityPrice).where(
                FactCommodityPrice.date_id == date_id,
                FactCommodityPrice.symbol == orm_fields["symbol"],
                FactCommodityPrice.source == orm_fields["source"],
            ),
        )
        db.add(FactCommodityPrice(**orm_fields))
        return PersistResult(ok=True, rows_affected=1)

    raise ValueError(f"unsupported sync persist table: {table}")


def write_batch_sync(
    db: Session,
    signed: SignedBatch | None,
    *,
    ctx: PersistContext,
) -> PersistResult:
    """Verify batch signature and insert all rows verbatim (sync Session)."""
    if signed is None:
        return _reject_persist(
            db,
            ctx=ctx,
            table="unknown",
            fields={},
            reject_reason="missing_signed_batch",
            signature_present=False,
            operation="insert",
        )

    reject_reason = _verify_signed_batch(signed)
    if reject_reason is not None:
        return _reject_persist(
            db,
            ctx=ctx,
            table=signed.table,
            fields={"rows": signed.rows},
            reject_reason=reject_reason,
            signature_present=bool(signed.signature),
            operation=signed.operation,
        )

    if signed.operation != "insert":
        return _reject_persist(
            db,
            ctx=ctx,
            table=signed.table,
            fields={"rows": signed.rows},
            reject_reason="unsupported_operation",
            signature_present=bool(signed.signature),
            operation=signed.operation,
        )

    model = _model_for_table(signed.table)
    instances = [
        model(**_orm_fields_for_table(signed.table, row))
        for row in signed.rows
    ]
    db.add_all(instances)
    return PersistResult(ok=True, rows_affected=len(instances))


async def write_async(
    db: AsyncSession,
    signed: SignedRecord | None,
    *,
    ctx: PersistContext,
) -> PersistResult:
    """Verify signature and write verbatim (async Session)."""
    if signed is None:
        write_reject_data(
            db.sync_session,
            source=ctx.source,
            table_target="unknown",
            reject_reason="missing_signed_record",
            raw_payload={},
            rejected_by="persist",
            marketplace_id=ctx.marketplace_id,
            listing_id=ctx.listing_id,
            signature_present=False,
            operation="insert",
        )
        return PersistResult(ok=False)

    reject_reason = _verify_signed_record(signed)
    if reject_reason is not None:
        write_reject_data(
            db.sync_session,
            source=ctx.source,
            table_target=signed.table,
            reject_reason=reject_reason,
            raw_payload=signed.fields,
            rejected_by="persist",
            marketplace_id=ctx.marketplace_id,
            listing_id=ctx.listing_id,
            signature_present=bool(signed.signature),
            operation=signed.operation,
        )
        return PersistResult(ok=False)

    if signed.operation == "delete":
        return await _write_async_delete(db, signed)

    orm_fields = _orm_fields_for_table(signed.table, signed.fields)
    table = signed.table
    date_id = orm_fields["date_id"]

    if table == "fact_currency_rate":
        await db.execute(
            delete(FactCurrencyRate).where(
                FactCurrencyRate.date_id == date_id,
                FactCurrencyRate.currency_code == orm_fields["currency_code"],
                FactCurrencyRate.source == orm_fields["source"],
            ),
        )
        db.add(FactCurrencyRate(**orm_fields))
        return PersistResult(ok=True, rows_affected=1)

    if table == "fact_crypto_price":
        await db.execute(
            delete(FactCryptoPrice).where(
                FactCryptoPrice.date_id == date_id,
                FactCryptoPrice.symbol == orm_fields["symbol"],
                FactCryptoPrice.source == orm_fields["source"],
            ),
        )
        db.add(FactCryptoPrice(**orm_fields))
        return PersistResult(ok=True, rows_affected=1)

    if table == "fact_commodity_price":
        await db.execute(
            delete(FactCommodityPrice).where(
                FactCommodityPrice.date_id == date_id,
                FactCommodityPrice.symbol == orm_fields["symbol"],
                FactCommodityPrice.source == orm_fields["source"],
            ),
        )
        db.add(FactCommodityPrice(**orm_fields))
        return PersistResult(ok=True, rows_affected=1)

    raise ValueError(f"unsupported async persist table: {table}")


MAX_ABS_PRICE_CHANGE_PCT = Decimal("9999.9999")
_PRICE_CHANGE_PCT_QUANT = Decimal("0.0001")


def compute_price_change_pct(
    new_price: float | Decimal,
    prior_last_price: float | Decimal | None,
) -> Decimal | None:
    """Percent delta from the listing's prior last_price to the new scrape price.

    Returns None when there is no prior price or the prior price is zero.
    Clamps to fact_price.price_change_pct Numeric(8,4) bounds.
    """
    if prior_last_price is None:
        return None

    prior = (
        prior_last_price
        if isinstance(prior_last_price, Decimal)
        else Decimal(str(prior_last_price))
    )
    if prior == 0:
        return None

    new = new_price if isinstance(new_price, Decimal) else Decimal(str(new_price))
    pct = (new - prior) / prior * Decimal("100")

    if pct > MAX_ABS_PRICE_CHANGE_PCT:
        pct = MAX_ABS_PRICE_CHANGE_PCT
    elif pct < -MAX_ABS_PRICE_CHANGE_PCT:
        pct = -MAX_ABS_PRICE_CHANGE_PCT

    return pct.quantize(_PRICE_CHANGE_PCT_QUANT, rounding=ROUND_HALF_UP)


def build_fact_price_fields(
    *,
    listing_id: UUID,
    date_id: int,
    price: float,
    currency_code: str,
    original_price: float | None,
    discount_pct: float | None,
    price_change_pct: float | None,
    scraped_at: datetime,
    scrape_job_id: UUID | None,
    price_eur: float | Decimal | None = None,
) -> dict[str, Any]:
    """Assemble the exact fact_price columns that the firewall signs."""
    fields: dict[str, Any] = {
        "listing_id": listing_id,
        "date_id": date_id,
        "price": price,
        "currency_code": currency_code,
        "original_price": original_price,
        "discount_pct": discount_pct,
        "price_change_pct": price_change_pct,
        "scraped_at": scraped_at,
        "scrape_job_id": scrape_job_id,
    }
    if price_eur is not None:
        fields["price_eur"] = float(price_eur)
    else:
        fields["price_eur"] = None
    return fields


def build_dim_product_fields(
    *,
    product_id: UUID,
    name: str,
    name_normalized: str,
    is_active: bool = True,
) -> dict[str, Any]:
    """Assemble the exact dim_product columns that the firewall signs."""
    return {
        "id": product_id,
        "name": name,
        "name_normalized": name_normalized,
        "is_active": is_active,
    }


def build_fact_listing_fields(
    *,
    product_id: UUID,
    marketplace_id: UUID,
    external_url: str,
    url_hash: str,
    is_active: bool = True,
    page_role: str = "product",
) -> dict[str, Any]:
    """Assemble the exact fact_listing columns that the firewall signs."""
    return {
        "product_id": product_id,
        "marketplace_id": marketplace_id,
        "external_url": external_url,
        "url_hash": url_hash,
        "is_active": is_active,
        "page_role": page_role,
    }
