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

import calendar
import logging
import re
from dataclasses import fields, is_dataclass
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from app.common.ops_alerts import emit_ops_alert
from app.database import invalidate_sync_session, is_read_only_sql_error
from app.models.dimensions import DimDate, DimProduct
from app.models.facts import FactListing
from app.modules.currency import resolve_price_eur
from app.modules.data_firewall.firewall import FirewallOutcome, evaluate_ecommerce, evaluate_market
from app.modules.data_firewall.quality_gate import assess_extracted
from app.modules.data_firewall.update_validator import authorize_scrape_update
from app.modules.ingestion.dto import IngestionResult
from app.modules.ingestion.gate import (
    MAX_CURRENCY_RAW_LEN,
    CurrencyResolver,
    disambiguate_currency,
)
from app.modules.ingestion.taxonomy import ensure_brand, ensure_category_chain
from app.modules.persist.scrape_gate_fields import (
    build_dim_date_fields,
    build_listing_update_fields,
    build_product_update_fields,
)
from app.modules.persist.writer import (
    PersistContext,
    build_fact_price_fields,
    compute_price_change_pct,
    write_sync,
)

logger = logging.getLogger(__name__)
slog = structlog.get_logger(__name__)


# --- adaptive scrape interval (SITEMAP_FIRST slice 3) ------------------------

BASE_SCRAPE_INTERVAL_MINUTES = 360
MAX_SCRAPE_INTERVAL_MINUTES = 10_080  # 7 days


def next_scrape_interval(current: int | None, *, price_changed: bool) -> int:
    """Adaptive backoff: quiet listings double their interval (capped at a
    week), a price change resets to the base cadence."""
    if price_changed:
        return BASE_SCRAPE_INTERVAL_MINUTES
    base = int(current or BASE_SCRAPE_INTERVAL_MINUTES)
    if base < BASE_SCRAPE_INTERVAL_MINUTES:
        base = BASE_SCRAPE_INTERVAL_MINUTES
    return min(base * 2, MAX_SCRAPE_INTERVAL_MINUTES)


# --- ingestion-owned helpers (moved verbatim from scraper.service) -----------


def _dim_date_row_for_day(today: date) -> dict[str, Any]:
    """Build the full dim_date insert payload for a calendar day."""
    date_id = int(today.strftime("%Y%m%d"))
    _, iso_week, iso_weekday = today.isocalendar()
    return build_dim_date_fields(
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


def _today_date_id(db: Session) -> int:
    """YYYYMMDD surrogate for dim_date; ensures row exists for FK on fact_price.

    Deadlock-safe: SELECT first, gate INSERT ... ON CONFLICT DO NOTHING if missing,
    then SELECT again (idempotent; concurrent workers do not block on add+flush).
    """
    today = datetime.now(timezone.utc).date()
    date_id = int(today.strftime("%Y%m%d"))
    row_id = db.execute(
        select(DimDate.date_id).where(DimDate.date_id == date_id),
    ).scalar_one_or_none()
    if row_id is not None:
        return date_id

    fields_row = _dim_date_row_for_day(today)
    outcome = evaluate_market(
        fields_row,
        table="dim_date",
        operation="insert",
        db=db,
        reject_source="ingestion_dim_date",
    )
    if outcome.passed and outcome.signed_record is not None:
        write_sync(
            db,
            outcome.signed_record,
            ctx=PersistContext(source="ingestion_dim_date", date_id=date_id),
        )
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
    ) -> bool:
        """Return True when extracted price/currency are identical to the last known state."""
        if listing.last_price is None or listing.last_currency_code is None:
            return False
        if new_price is None or new_currency is None:
            return False

        price_same = abs(float(new_price) - float(listing.last_price)) < 0.001
        currency_same = (
            new_currency.strip().upper() == listing.last_currency_code.strip().upper()
        )
        return price_same and currency_same

    def _persist_scrape_update(
        self,
        *,
        table: str,
        kind: str,
        fields: dict[str, Any],
        listing: FactListing,
        source: str,
        date_id: int | None = None,
        sync_instance: Any | None = None,
    ) -> bool:
        """Authorize a scrape UPDATE delta and write via persist on this session."""
        outcome = authorize_scrape_update(
            table=table,
            kind=kind,
            fields=fields,
            db=self.db,
            reject_source=source,
        )
        if not outcome.passed or outcome.signed_record is None:
            return False
        result = write_sync(
            self.db,
            outcome.signed_record,
            ctx=PersistContext(
                source=source,
                marketplace_id=listing.marketplace_id,
                listing_id=listing.id,
                date_id=date_id,
            ),
        )
        if result.ok:
            # Seam-3 contract (mirrors scraper service): same-session readers
            # must see the gated UPDATE on the ORM instance immediately;
            # committed-value assignment avoids a shadow ORM UPDATE.
            target = sync_instance
            if target is None and table == "fact_listing":
                target = listing
            if target is not None:
                for key, value in fields.items():
                    if key in ("url_hash", "id") or not hasattr(target, key):
                        continue
                    try:
                        set_committed_value(target, key, value)
                    except Exception:  # non-ORM stub in unit tests
                        setattr(target, key, value)
        return result.ok

    def persist_extracted(
        self,
        *,
        data: Any,
        listing: FactListing,
        scrape_job_id: UUID | None = None,
    ) -> IngestionResult:
        """Run firewall -> (optional) signed persist -> commit."""
        slog.info(
            "EXTRACTED_DATA",
            line="EXTRACTED DATA → product_name/title/price/currency",
            product_name=getattr(data, "product_name", None),
            title=getattr(data, "title", None),
            price=getattr(data, "price", None),
            currency=getattr(data, "currency", None),
        )

        self._enrich_dim_product(data, listing)

        currency_raw_text = getattr(data, "currency_raw", None) or ""
        curr_raw = getattr(data, "currency", None)
        if curr_raw:
            resolved_code = disambiguate_currency(
                str(curr_raw),
                currency_raw_text or getattr(data, "price_raw_text", None),
                self._currency_resolver.whitelist_for(listing.marketplace_id),
            )
            if resolved_code and resolved_code != curr_raw:
                slog.info(
                    "currency_token_disambiguated",
                    detected=str(curr_raw),
                    resolved=resolved_code,
                    marketplace_id=str(listing.marketplace_id),
                )
                data.currency = resolved_code
                curr_raw = resolved_code

        persist_fields: dict[str, Any] | None = None
        scrape_price_eur: float | None = None
        if getattr(data, "price", None) is not None and curr_raw:
            now = datetime.now(tz=timezone.utc)
            date_id = _today_date_id(self.db)
            currency_code = str(curr_raw)
            resolved_eur = resolve_price_eur(
                price=float(data.price),
                currency_code=currency_code,
                date_id=date_id,
                db=self.db,
            )
            scrape_price_eur = float(resolved_eur) if resolved_eur is not None else None
            original_price_value = (
                float(data.original_price)
                if getattr(data, "original_price", None) is not None
                else None
            )
            price_change_pct_value = compute_price_change_pct(
                new_price=data.price,
                prior_last_price=listing.last_price,
            )
            persist_fields = build_fact_price_fields(
                listing_id=listing.id,
                date_id=date_id,
                price=float(data.price),
                currency_code=currency_code,
                original_price=original_price_value,
                discount_pct=None,
                price_change_pct=(
                    float(price_change_pct_value)
                    if price_change_pct_value is not None
                    else None
                ),
                scraped_at=now,
                scrape_job_id=scrape_job_id,
                price_eur=scrape_price_eur,
            )

        if (
            getattr(data, "title", None) is None
            and getattr(data, "price", None) is None
            and getattr(data, "page_role", None) == "product"
        ):
            emit_ops_alert(
                module="parser",
                submodule="extraction",
                severity="warning",
                anomaly_type="extraction_empty",
                message=(
                    "Extraction yielded no title and no price for a product page "
                    f"marketplace_id={listing.marketplace_id}"
                ),
                entity=str(listing.marketplace_id),
                context={"marketplace_id": str(listing.marketplace_id)},
            )

        assess_extracted(
            data,
            url=listing.external_url,
            allowed_currencies=self._currency_resolver.whitelist_for(
                listing.marketplace_id
            ),
            marketplace_id=listing.marketplace_id,
        )

        outcome = evaluate_ecommerce(
            data,
            marketplace_id=listing.marketplace_id,
            currency_resolver=self._currency_resolver,
            page_role=getattr(data, "page_role", None),
            persist_fields=persist_fields,
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
            ):
                now = datetime.now(tz=timezone.utc)
                normalized_currency = (
                    persist_fields["currency_code"] if persist_fields else None
                )
                denorm_delta = {
                    "last_checked_at": now,
                    "last_price": data.price,
                    "last_currency_code": normalized_currency,
                    "last_price_eur": scrape_price_eur,
                    "scrape_interval_minutes": next_scrape_interval(
                        getattr(listing, "scrape_interval_minutes", None),
                        price_changed=False,
                    ),
                }
                denorm_fields = build_listing_update_fields(
                    url_hash=listing.url_hash,
                    **denorm_delta,
                )
                self._persist_scrape_update(
                    table="fact_listing",
                    kind="listing_denorm_no_change",
                    fields=denorm_fields,
                    listing=listing,
                    source="ingestion_denorm_no_change",
                )
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
                    denorm_delta = {
                        "last_price": data.price,
                        "last_currency_code": persist_fields["currency_code"],
                        "last_price_changed_at": persist_fields["scraped_at"],
                        "last_price_eur": scrape_price_eur,
                        # Mirror of this fact_price row's pct: list endpoints
                        # read it O(1) instead of windowing all of fact_price.
                        "last_price_change_pct": persist_fields["price_change_pct"],
                        "scrape_interval_minutes": next_scrape_interval(
                            getattr(listing, "scrape_interval_minutes", None),
                            price_changed=True,
                        ),
                    }
                    denorm_fields = build_listing_update_fields(
                        url_hash=listing.url_hash,
                        **denorm_delta,
                    )
                    self._persist_scrape_update(
                        table="fact_listing",
                        kind="listing_denorm_success",
                        fields=denorm_fields,
                        listing=listing,
                        source="ingestion_denorm_success",
                        date_id=persist_fields["date_id"],
                    )
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
        result = IngestionResult(
            persisted=persisted,
            log_status=forced_log_status,
            skip_reason=outcome.skip_reason,
            price_found=price_found,
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
                    read_only_failed=True,
                )
            return IngestionResult(
                persisted=False,
                log_status=forced_log_status,
                skip_reason=outcome.skip_reason,
                price_found=price_found,
                persist_failed=True,
            )

        return result

    def _enrich_dim_product(self, data: Any, listing: FactListing) -> None:
        """Gate-route DimProduct.name / image_url per placeholder-replacement rules."""
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

        delta: dict[str, Any] = {}
        if label:
            if not pn_nonempty:
                delta["name"] = label[:500]
                delta["name_normalized"] = _normalize_product_name(label)
            elif _should_replace_placeholder_name(product.name, listing.external_url):
                delta["name"] = label[:500]
                delta["name_normalized"] = _normalize_product_name(label)

        image_url = getattr(data, "image_url", None)
        if image_url and not product.image_url:
            delta["image_url"] = image_url

        # Cross-shop identity: gtin -> sku_universal, mpn -> mpn. Write-once
        # (first PDP scrape wins); the matching tick's gtin sweep upgrades
        # match groups from these later.
        gtin = getattr(data, "gtin", None)
        if (
            isinstance(gtin, str)
            and gtin.strip()
            and not getattr(product, "sku_universal", None)
        ):
            delta["sku_universal"] = gtin.strip()[:100]
        mpn = getattr(data, "mpn", None)
        if (
            isinstance(mpn, str)
            and mpn.strip()
            and not getattr(product, "mpn", None)
        ):
            delta["mpn"] = mpn.strip()[:100]

        brand_name = getattr(data, "brand", None)
        if (
            isinstance(brand_name, str)
            and brand_name.strip()
            and getattr(product, "brand_id", None) is None
        ):
            brand_id = ensure_brand(self.db, brand_name)
            if brand_id is not None:
                delta["brand_id"] = str(brand_id)

        description = getattr(data, "description", None)
        if isinstance(description, str) and description.strip():
            existing_attrs = (
                dict(product.attributes)
                if isinstance(getattr(product, "attributes", None), dict)
                else {}
            )
            if not existing_attrs.get("description"):
                existing_attrs["description"] = description.strip()[:2000]
                delta["attributes"] = existing_attrs

        category_path = getattr(data, "category_path", None)
        if (
            isinstance(category_path, list)
            and category_path
            and getattr(product, "category_id", None) is None
        ):
            category_id = ensure_category_chain(self.db, category_path)
            if category_id is not None:
                delta["category_id"] = str(category_id)

        if not delta:
            return

        enrich_fields = build_product_update_fields(
            product_id=listing.product_id,
            **delta,
        )
        self._persist_scrape_update(
            table="dim_product",
            kind="product_enrich",
            fields=enrich_fields,
            listing=listing,
            source="ingestion_product_enrich",
            sync_instance=product,
        )

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
