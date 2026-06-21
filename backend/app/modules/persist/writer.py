"""Mutation-free persistence — verify HMAC then write verbatim."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.facts import (
    FactCommodityPrice,
    FactCryptoPrice,
    FactCurrencyRate,
    FactPrice,
)
from app.modules.data_firewall.reject_store import write_reject_data
from app.modules.data_firewall.signing import SignedRecord, verify
from app.observability.sentry_init import capture_exception_if_initialized

logger = logging.getLogger(__name__)
slog = structlog.get_logger(__name__)


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
    if "scraped_at" in out:
        out["scraped_at"] = _parse_datetime(out["scraped_at"])
    if "fetched_at" in out:
        out["fetched_at"] = _parse_datetime(out["fetched_at"])
    return out


def _reject_persist(
    db: Session,
    *,
    ctx: PersistContext,
    table: str,
    fields: dict[str, Any],
    reject_reason: str,
    signature_present: bool,
) -> bool:
    slog.error(
        "firewall_flag_missing",
        table=table,
        source=ctx.source,
        reject_reason=reject_reason,
        signature_present=signature_present,
    )
    try:
        import sentry_sdk

        if sentry_sdk.is_initialized():
            sentry_sdk.capture_message(
                "firewall_flag_missing",
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
    )
    return False


def write_sync(
    db: Session,
    signed: SignedRecord | None,
    *,
    ctx: PersistContext,
) -> bool:
    """Verify signature and write verbatim to the target fact table (sync Session)."""
    if signed is None:
        return _reject_persist(
            db,
            ctx=ctx,
            table="unknown",
            fields={},
            reject_reason="missing_signed_record",
            signature_present=False,
        )

    if not verify(signed.fields, signed.signature):
        return _reject_persist(
            db,
            ctx=ctx,
            table=signed.table,
            fields=signed.fields,
            reject_reason="invalid_signature",
            signature_present=bool(signed.signature),
        )

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
        return True

    raise ValueError(f"unsupported sync persist table: {table}")


async def write_async(
    db: AsyncSession,
    signed: SignedRecord | None,
    *,
    ctx: PersistContext,
) -> bool:
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
        )
        return False

    if not verify(signed.fields, signed.signature):
        write_reject_data(
            db.sync_session,
            source=ctx.source,
            table_target=signed.table,
            reject_reason="invalid_signature",
            raw_payload=signed.fields,
            rejected_by="persist",
            marketplace_id=ctx.marketplace_id,
            listing_id=ctx.listing_id,
            signature_present=bool(signed.signature),
        )
        return False

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
        return True

    if table == "fact_crypto_price":
        await db.execute(
            delete(FactCryptoPrice).where(
                FactCryptoPrice.date_id == date_id,
                FactCryptoPrice.symbol == orm_fields["symbol"],
                FactCryptoPrice.source == orm_fields["source"],
            ),
        )
        db.add(FactCryptoPrice(**orm_fields))
        return True

    if table == "fact_commodity_price":
        await db.execute(
            delete(FactCommodityPrice).where(
                FactCommodityPrice.date_id == date_id,
                FactCommodityPrice.symbol == orm_fields["symbol"],
                FactCommodityPrice.source == orm_fields["source"],
            ),
        )
        db.add(FactCommodityPrice(**orm_fields))
        return True

    raise ValueError(f"unsupported async persist table: {table}")


def build_fact_price_fields(
    *,
    listing_id: UUID,
    date_id: int,
    price: float,
    currency_code: str,
    original_price: float | None,
    discount_pct: float | None,
    in_stock: bool | None,
    price_change_pct: float | None,
    scraped_at: datetime,
    scrape_job_id: UUID | None,
) -> dict[str, Any]:
    """Assemble the exact fact_price columns that the firewall signs."""
    return {
        "listing_id": listing_id,
        "date_id": date_id,
        "price": price,
        "currency_code": currency_code,
        "original_price": original_price,
        "discount_pct": discount_pct,
        "in_stock": in_stock,
        "price_change_pct": price_change_pct,
        "scraped_at": scraped_at,
        "scrape_job_id": scrape_job_id,
    }
