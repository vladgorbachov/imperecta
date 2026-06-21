"""IngestionService — write-and-enrich half of the pool scrape pipeline.

Receives ``ExtractedProduct`` from the parser (scraper) and runs the
data_firewall; on pass signs fields and delegates verbatim write to
persist_module. Enriches DimProduct (name + image), and updates the
FactListing's denormalised price fields. Commits its own transaction
(decision A). Returns an immutable ``IngestionResult`` the parser uses to
shape its separate ScrapeLog write.

Strict scope: ingestion does NOT import scraper/pool/extractor code —
one-directional edge parser -> ingestion only. The ``ExtractedProduct``
contract is consumed via duck-typed attribute access on ``data``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.database import invalidate_sync_session, is_read_only_sql_error
from app.models.dimensions import DimProduct
from app.models.facts import FactListing
from app.modules.data_firewall.firewall import FirewallOutcome, evaluate_ecommerce
from app.modules.ingestion.dto import IngestionResult
from app.modules.ingestion.gate import MAX_CURRENCY_RAW_LEN, CurrencyResolver
from app.modules.persist.writer import PersistContext, build_fact_price_fields, write_sync

logger = logging.getLogger(__name__)
slog = structlog.get_logger(__name__)


# --- ingestion-owned helpers (moved verbatim from scraper.service) -----------


def _today_date_id(db: Session) -> int:
    """YYYYMMDD surrogate for dim_date; ensures row exists for FK on fact_price.

    Deadlock-safe: SELECT first, INSERT ... ON CONFLICT DO NOTHING if missing,
    then SELECT again (idempotent; concurrent workers do not block on add+flush).
    """
    import calendar

    from app.models.dimensions import DimDate

    today = datetime.now(timezone.utc).date()
    date_id = int(today.strftime("%Y%m%d"))
    row_id = db.execute(
        select(DimDate.date_id).where(DimDate.date_id == date_id),
    ).scalar_one_or_none()
    if row_id is not None:
        return date_id

    _, iso_week, iso_weekday = today.isocalendar()
    stmt = (
        pg_insert(DimDate)
        .values(
            date_id=date_id,
            full_date=today,
            year=today.year,
            quarter=(today.month - 1) // 3 + 1,
            month=today.month,
            month_name=today.strftime("%B"),
            week_iso=iso_week,
            day_of_month=today.day,
            day_of_week=iso_weekday,
            day_name=today.strftime("%A"),
            is_weekend=iso_weekday >= 6,
            is_last_day_of_month=today.day
            == calendar.monthrange(today.year, today.month)[1],
        )
        .on_conflict_do_nothing(index_elements=["date_id"])
    )
    db.execute(stmt)
    db.flush()

    row_id = db.execute(
        select(DimDate.date_id).where(DimDate.date_id == date_id),
    ).scalar_one_or_none()
    if row_id is None:
        raise RuntimeError(f"dim_date row missing after upsert for date_id={date_id}")
    return date_id


def _normalize_product_name(raw: str) -> str:
    s = (raw or "").lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s[:500]


def _should_replace_placeholder_name(name: str | None, external_url: str) -> bool:
    """True if dim_product.name is a discovery placeholder; scraped title should replace it."""
    n = (name or "").strip()
    if not n or n.lower() == "product":
        return True
    if n == external_url:
        return True
    compact = n.replace(" ", "").replace("-", "").replace("_", "")
    if compact.isdigit():
        return True
    return False


def _payload_has_product_name_field(payload: object) -> bool:
    """True when extractor dataclass defines product_name (strict log rules apply)."""
    if not is_dataclass(payload):
        return False
    return any(f.name == "product_name" for f in fields(payload))


# --- IngestionService --------------------------------------------------------


class IngestionService:
    """data_firewall + persist_module + DimProduct enrichment.

    Single public method: ``persist_extracted``. Owns its own commit
    (decision A). Does NOT write to scrape_logs; that stays with the parser.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self._currency_resolver = CurrencyResolver(db)

    @staticmethod
    def _should_skip_price_record(
        listing: FactListing,
        new_price: float | None,
        new_currency: str | None,
        new_in_stock: bool | None,
    ) -> bool:
        """Return True when extracted values are identical to the last known state."""
        if listing.last_price is None or listing.last_currency_code is None:
            return False
        if new_price is None or new_currency is None:
            return False

        price_same = abs(float(new_price) - float(listing.last_price)) < 0.001
        currency_same = (
            new_currency.strip().upper() == listing.last_currency_code.strip().upper()
        )
        if new_in_stock is None and listing.last_in_stock is None:
            stock_same = True
        elif new_in_stock is None or listing.last_in_stock is None:
            stock_same = False
        else:
            stock_same = bool(new_in_stock) == bool(listing.last_in_stock)
        return price_same and currency_same and stock_same

    def persist_extracted(
        self,
        *,
        data: Any,
        listing: FactListing,
        extracted_in_stock: bool | None,
        scrape_job_id: UUID | None = None,
    ) -> IngestionResult:
        """Run firewall -> (optional) signed persist -> commit."""
        slog.info(
            "EXTRACTED_DATA",
            line="EXTRACTED DATA → product_name/title/price/currency/in_stock",
            product_name=getattr(data, "product_name", None),
            title=getattr(data, "title", None),
            price=getattr(data, "price", None),
            currency=getattr(data, "currency", None),
            in_stock=extracted_in_stock,
        )

        self._enrich_dim_product(data, listing)

        currency_raw_text = getattr(data, "currency_raw", None) or ""
        curr_raw = getattr(data, "currency", None)

        persist_fields: dict[str, Any] | None = None
        if getattr(data, "price", None) is not None and curr_raw:
            now = datetime.now(tz=timezone.utc)
            date_id = _today_date_id(self.db)
            original_price_value = (
                float(data.original_price)
                if getattr(data, "original_price", None) is not None
                else None
            )
            persist_fields = build_fact_price_fields(
                listing_id=listing.id,
                date_id=date_id,
                price=float(data.price),
                currency_code=str(curr_raw),
                original_price=original_price_value,
                discount_pct=getattr(data, "discount_pct", None),
                in_stock=extracted_in_stock,
                price_change_pct=getattr(data, "price_change_pct", None),
                scraped_at=now,
                scrape_job_id=scrape_job_id,
            )

        outcome = evaluate_ecommerce(
            data,
            marketplace_id=listing.marketplace_id,
            currency_resolver=self._currency_resolver,
            page_role=getattr(data, "page_role", None),
            persist_fields=persist_fields,
            extracted_in_stock=extracted_in_stock,
            db=self.db,
            listing_id=listing.id,
        )

        slog.info(
            "PERSISTENCE_GATE",
            line="PERSISTENCE GATE → product_name_ok / price_ok / currency_ok / sane / country",
            product_name_ok=outcome.product_name_ok,
            price_ok=outcome.price_ok,
            currency_ok=outcome.currency_ok,
            currency_raw_sane_ok=outcome.currency_raw_sane_ok,
            currency_country_match_ok=outcome.currency_country_match_ok,
            price_raw_text=getattr(data, "price_raw_text", None),
            currency_raw=currency_raw_text[:200] if currency_raw_text else None,
            detected_currency=curr_raw,
        )

        forced_log_status: str | None = None
        persisted = False

        if not outcome.passed:
            self._log_gate_rejection(outcome, listing, currency_raw_text, curr_raw)
            forced_log_status = outcome.forced_log_status
        else:
            if self._should_skip_price_record(
                listing,
                data.price,
                data.currency,
                extracted_in_stock,
            ):
                listing.last_checked_at = datetime.now(tz=timezone.utc)
                listing.last_price = data.price
                listing.last_currency_code = data.currency if data.currency else None
                listing.last_in_stock = extracted_in_stock
                forced_log_status = "no_change"
                logger.info(
                    "PRICE_UNCHANGED listing_id=%s price=%s %s",
                    listing.id,
                    data.price,
                    data.currency,
                )
            else:
                wrote = write_sync(
                    self.db,
                    outcome.signed_record,
                    ctx=PersistContext(
                        source="ecommerce_scrape",
                        marketplace_id=listing.marketplace_id,
                        listing_id=listing.id,
                        date_id=persist_fields["date_id"] if persist_fields else None,
                    ),
                )
                if wrote and persist_fields:
                    listing.last_price = data.price
                    listing.last_currency_code = persist_fields["currency_code"]
                    listing.last_in_stock = extracted_in_stock
                    listing.last_price_changed_at = persist_fields["scraped_at"]
                    forced_log_status = "success"
                    persisted = True
                    logger.info(
                        "fact_price write listing_id=%s date_id=%s currency=%s",
                        listing.id,
                        persist_fields["date_id"],
                        persist_fields["currency_code"],
                    )
                else:
                    forced_log_status = "persist_failed"
                    persisted = False

        price_found = (
            float(data.price)
            if getattr(data, "price", None) is not None
            else None
        )
        in_stock_found = extracted_in_stock
        result = IngestionResult(
            persisted=persisted,
            log_status=forced_log_status,
            skip_reason=outcome.skip_reason,
            price_found=price_found,
            in_stock_found=in_stock_found,
            persist_failed=False,
        )

        slog.info(
            "FINAL_PERSIST",
            line=(
                f"FINAL PERSIST → listing_id={listing.id} status={forced_log_status} "
                f"price={getattr(data, 'price', None)!s}"
            ),
            listing_id=str(listing.id),
            product_name=getattr(data, "product_name", None),
            title=getattr(data, "title", None),
            price=getattr(data, "price", None),
            currency=getattr(data, "currency", None),
            in_stock=extracted_in_stock,
            status=forced_log_status,
        )

        try:
            self.db.flush()
            self.db.commit()
        except Exception as exc:
            logger.error(
                "ingestion persist rollback listing_id=%s err=%s",
                listing.id,
                exc,
                exc_info=True,
            )
            self.db.rollback()
            if is_read_only_sql_error(exc):
                invalidate_sync_session(self.db)
                return IngestionResult(
                    persisted=False,
                    log_status=forced_log_status,
                    skip_reason=outcome.skip_reason,
                    price_found=price_found,
                    in_stock_found=in_stock_found,
                    read_only_failed=True,
                )
            return IngestionResult(
                persisted=False,
                log_status=forced_log_status,
                skip_reason=outcome.skip_reason,
                price_found=price_found,
                in_stock_found=in_stock_found,
                persist_failed=True,
            )

        return result

    def _enrich_dim_product(self, data: Any, listing: FactListing) -> None:
        """Update DimProduct.name / image_url per the placeholder-replacement rules."""
        product = self.db.get(DimProduct, listing.product_id)
        if not product:
            return

        pn = getattr(data, "product_name", None)
        tt = getattr(data, "title", None)
        pn_nonempty = bool(pn and str(pn).strip())
        if pn_nonempty:
            label = str(pn).strip()[:500]
        elif tt and str(tt).strip():
            label = str(tt).strip()[:500]
        else:
            label = None

        if label:
            if not pn_nonempty:
                product.name = label[:500]
                product.name_normalized = _normalize_product_name(label)
            elif _should_replace_placeholder_name(product.name, listing.external_url):
                product.name = label[:500]
                product.name_normalized = _normalize_product_name(label)

        image_url = getattr(data, "image_url", None)
        if image_url and not product.image_url:
            product.image_url = image_url

    @staticmethod
    def _log_gate_rejection(
        outcome: FirewallOutcome,
        listing: FactListing,
        currency_raw_text: str,
        curr_raw: str | None,
    ) -> None:
        """Emit the same per-reason log lines the inline gate used to."""
        if not outcome.product_name_ok or not outcome.currency_ok:
            logger.info(
                "fact_price skipped: missing product_name or currency (listing_id=%s)",
                listing.id,
            )
        elif not outcome.currency_raw_sane_ok:
            logger.info(
                "fact_price skipped: currency_raw too long (likely glued text) "
                "listing_id=%s len=%d",
                listing.id,
                len(currency_raw_text),
            )
        elif not outcome.currency_country_match_ok:
            logger.info(
                "fact_price skipped: currency=%s not allowed for marketplace_id=%s",
                curr_raw,
                listing.marketplace_id,
            )


__all__ = [
    "IngestionService",
    "MAX_CURRENCY_RAW_LEN",
    "_today_date_id",
    "_normalize_product_name",
    "_should_replace_placeholder_name",
    "_payload_has_product_name_field",
]
