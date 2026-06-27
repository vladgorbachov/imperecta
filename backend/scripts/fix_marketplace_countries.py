"""One-time gated correction for mislabeled marketplace country codes.

Usage (from backend/, after migration 033 is applied):

    python -m scripts.fix_marketplace_countries

Reads marketplace rows via async session; writes ONLY through write_meta_async
(evaluate_market update → write_sync). Idempotent — safe to re-run.
"""

from __future__ import annotations

import asyncio
import sys
from uuid import UUID

import structlog
from sqlalchemy import select

from app.database import async_session_maker
from app.models.dimensions import DimCountry, DimMarketplace
from app.modules.persist.meta_write import build_dim_marketplace_fields, write_meta_async

slog = structlog.get_logger(__name__)

CORRECTIONS: list[tuple[str, str]] = [
    ("organic-shop.com", "MD"),
    ("amazon.com", "ZZ"),
    ("bol.com", "NL"),
]


async def _lookup_marketplace(session, domain: str) -> tuple[UUID, str] | None:
    """Return (marketplace_id, current country_code) for domain, or None."""
    row = await session.execute(
        select(DimMarketplace.id, DimMarketplace.country_code).where(
            DimMarketplace.domain == domain,
        ),
    )
    match = row.one_or_none()
    if match is None:
        return None
    return match.id, str(match.country_code)


async def _lookup_country_currency(session, country_code: str) -> str | None:
    """Return dim_country.currency_code for an active reference row."""
    currency = await session.scalar(
        select(DimCountry.currency_code).where(
            DimCountry.country_code == country_code,
        ),
    )
    return str(currency) if currency else None


async def run_corrections() -> int:
    """Apply gated country corrections; return exit code (0 ok, 1 had failures)."""
    failures = 0
    async with async_session_maker() as session:
        for domain, target_code in CORRECTIONS:
            lookup = await _lookup_marketplace(session, domain)
            if lookup is None:
                slog.warning("marketplace_not_found", domain=domain)
                failures += 1
                continue

            marketplace_id, current_code = lookup
            if current_code == target_code:
                slog.info(
                    "marketplace_already_correct",
                    domain=domain,
                    country_code=target_code,
                )
                continue

            currency_code = await _lookup_country_currency(session, target_code)
            if currency_code is None:
                slog.error(
                    "target_country_missing",
                    domain=domain,
                    target_country_code=target_code,
                )
                failures += 1
                continue

            fields = build_dim_marketplace_fields(
                id=marketplace_id,
                country_code=target_code,
                operates_in=[target_code],
                currency_code=currency_code,
            )
            result = await write_meta_async(
                table="dim_marketplace",
                operation="update",
                fields=fields,
                reject_source="marketplaces",
            )
            if not result.ok:
                slog.error(
                    "marketplace_correction_rejected",
                    domain=domain,
                    marketplace_id=str(marketplace_id),
                    from_country=current_code,
                    to_country=target_code,
                )
                failures += 1
                continue

            slog.info(
                "marketplace_country_corrected",
                domain=domain,
                marketplace_id=str(marketplace_id),
                from_country=current_code,
                to_country=target_code,
                currency_code=currency_code,
                rows_affected=result.rows_affected,
            )

    return 1 if failures else 0


async def main() -> None:
    exit_code = await run_corrections()
    if exit_code != 0:
        sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())
