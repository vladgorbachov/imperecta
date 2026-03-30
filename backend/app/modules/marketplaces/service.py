"""Marketplace pool: dim_marketplace quotas, CRUD, and discovery helpers."""

from __future__ import annotations

import hashlib
import logging
import re
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dimensions import DimCountry, DimCurrency, DimMarketplace
from app.models.facts import FactListing

logger = logging.getLogger(__name__)


class MarketplacePoolService:
    """Maintain products_in_pool from fact_listing and expose dim_marketplace reads."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def recalculate_all_quotas(self) -> None:
        """Set products_in_pool to active listing counts per marketplace."""
        stmt = (
            select(FactListing.marketplace_id, func.count(FactListing.id))
            .where(FactListing.is_active.is_(True))
            .group_by(FactListing.marketplace_id)
        )
        result = await self.db.execute(stmt)
        rows = result.all()
        for marketplace_id, cnt in rows:
            await self.db.execute(
                update(DimMarketplace)
                .where(DimMarketplace.id == marketplace_id)
                .values(products_in_pool=int(cnt)),
            )
        await self.db.commit()
        logger.info("recalculate_all_quotas updated %d marketplaces", len(rows))

    async def list_active_marketplaces(self) -> list[DimMarketplace]:
        """All active rows from dim_marketplace (workers / admin)."""
        result = await self.db.execute(
            select(DimMarketplace)
            .where(DimMarketplace.is_active.is_(True))
            .order_by(DimMarketplace.marketplace_code),
        )
        return list(result.scalars().all())

    async def get_by_id(self, marketplace_id: UUID) -> DimMarketplace | None:
        """Load one marketplace by primary key."""
        result = await self.db.execute(
            select(DimMarketplace).where(DimMarketplace.id == marketplace_id),
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, marketplace_code: str) -> DimMarketplace | None:
        """Load marketplace by stable code (replaces legacy int marketplace_id)."""
        code = (marketplace_code or "").strip()
        if not code:
            return None
        result = await self.db.execute(
            select(DimMarketplace).where(DimMarketplace.marketplace_code == code),
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _normalize_url(url: str) -> str:
        raw = (url or "").strip()
        if not raw:
            raise ValueError("URL is empty")
        if "://" not in raw:
            raw = f"https://{raw}"
        parsed = urlparse(raw)
        host = (parsed.netloc or parsed.path).lower().strip()
        if not host:
            raise ValueError("Invalid URL: could not extract domain")
        if "@" in host:
            host = host.split("@", 1)[1]
        host = host.split(":", 1)[0].strip("/")
        if host.startswith("www."):
            host = host[4:]
        if not host:
            raise ValueError("Invalid URL: could not extract domain")
        return f"https://{host}"


# TLD → ISO country code hints (geography only, not marketplace names).
_TLD_TO_COUNTRY: dict[str, str] = {
    "ru": "RU",
    "ua": "UA",
    "by": "BY",
    "kz": "KZ",
    "uz": "UZ",
    "md": "MD",
    "ge": "GE",
    "am": "AM",
    "az": "AZ",
    "kg": "KG",
    "tj": "TJ",
    "de": "DE",
    "pl": "PL",
    "fr": "FR",
    "nl": "NL",
    "cz": "CZ",
    "sk": "SK",
    "at": "AT",
    "lv": "LV",
    "lt": "LT",
    "ee": "EE",
    "ro": "RO",
    "hu": "HU",
    "bg": "BG",
    "hr": "HR",
    "si": "SI",
    "gr": "GR",
    "it": "IT",
    "es": "ES",
    "pt": "PT",
    "rs": "RS",
    "ba": "BA",
    "mk": "MK",
    "me": "ME",
    "al": "AL",
    "tr": "TR",
    "fi": "FI",
    "se": "SE",
    "dk": "DK",
    "no": "NO",
    "uk": "UK",
    "ch": "CH",
    "be": "BE",
    "ie": "IE",
    "com": "US",
    "net": "US",
    "org": "US",
}


class MarketplaceService:
    """CRUD and helpers for dim_marketplace (admin)."""

    _UPDATE_KEYS = frozenset(
        {
            "requires_js",
            "is_active",
            "product_quota",
            "name",
            "rate_limit_delay",
            "custom_product_link_selector",
            "custom_next_page_selector",
            "custom_price_selector",
            "custom_title_selector",
            "scraper_type",
            "locale",
        }
    )

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_marketplaces(self) -> list[DimMarketplace]:
        """All marketplaces ordered by name."""
        result = await self.db.execute(select(DimMarketplace).order_by(DimMarketplace.name))
        return list(result.scalars().all())

    async def get_marketplace(self, marketplace_id: UUID) -> DimMarketplace | None:
        return await self.db.get(DimMarketplace, marketplace_id)

    @staticmethod
    def _tld_to_country(tld: str) -> str:
        return _TLD_TO_COUNTRY.get(tld.lower(), "DE")

    @staticmethod
    def _make_marketplace_code(domain: str) -> str:
        raw = re.sub(r"[^a-z0-9._-]", "_", domain.lower().replace(".", "_"))
        if len(raw) <= 50:
            return raw
        digest = hashlib.sha256(domain.encode()).hexdigest()[:10]
        return f"{raw[:39]}_{digest}"[:50]

    async def _country_exists(self, country_code: str) -> bool:
        q = await self.db.scalar(
            select(func.count())
            .select_from(DimCountry)
            .where(DimCountry.country_code == country_code),
        )
        return bool(q)

    async def _fallback_country_code(self) -> str:
        row = await self.db.scalar(
            select(DimCountry.country_code).where(DimCountry.country_code == "DE"),
        )
        if row:
            return "DE"
        any_code = await self.db.scalar(select(DimCountry.country_code).limit(1))
        return any_code or "DE"

    async def _resolve_country_and_currency(self, domain: str) -> tuple[str, str]:
        parts = domain.lower().split(".")
        tld = parts[-1] if len(parts) >= 2 else ""
        candidate = self._tld_to_country(tld)
        if await self._country_exists(candidate):
            cc_row = await self.db.execute(
                select(DimCountry.currency_code).where(DimCountry.country_code == candidate)
            )
            cur = cc_row.scalar_one()
            if await self._currency_exists(cur):
                return candidate, cur
        fb = await self._fallback_country_code()
        cc_row = await self.db.execute(
            select(DimCountry.currency_code).where(DimCountry.country_code == fb),
        )
        cur = cc_row.scalar_one()
        if not await self._currency_exists(cur):
            cur = "EUR"
        return fb, cur

    async def _currency_exists(self, code: str) -> bool:
        q = await self.db.scalar(
            select(func.count()).select_from(DimCurrency).where(DimCurrency.currency_code == code)
        )
        return bool(q)

    async def add_by_url(self, url: str) -> tuple[DimMarketplace, bool]:
        """Add marketplace from URL: extract domain, infer country/currency from TLD + dim_country.

        Returns (row, is_new). Duplicate domain returns existing row with is_new=False.
        """
        base = MarketplacePoolService._normalize_url(url)
        parsed = urlparse(base)
        domain = (parsed.netloc or "").lower()
        if not domain:
            raise ValueError("Invalid URL: empty host")

        existing = await self.db.scalar(
            select(DimMarketplace).where(DimMarketplace.domain == domain),
        )
        if existing:
            return existing, False

        country_code, currency_code = await self._resolve_country_and_currency(domain)
        marketplace_code = self._make_marketplace_code(domain)
        code_taken = await self.db.scalar(
            select(DimMarketplace.id).where(DimMarketplace.marketplace_code == marketplace_code)
        )
        if code_taken:
            suffix = hashlib.sha256(domain.encode()).hexdigest()[:8]
            marketplace_code = f"{marketplace_code[:41]}_{suffix}"[:50]

        label = domain.split(".")[0]
        name = label[:1].upper() + label[1:] if label else domain

        mp = DimMarketplace(
            marketplace_code=marketplace_code,
            name=name[:200],
            source_type="marketplace",
            country_code=country_code,
            operates_in=[country_code],
            domain=domain[:255],
            base_url=base,
            api_available=False,
            currency_code=currency_code,
            scraper_type="web_api",
            is_active=True,
        )
        self.db.add(mp)
        await self.db.commit()
        await self.db.refresh(mp)
        return mp, True

    async def import_from_text(self, content: str) -> dict:
        """Import marketplaces from text (one URL per line)."""
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        added = 0
        skipped = 0
        errors: list[str] = []

        for line in lines:
            if line.startswith("#"):
                continue
            try:
                _mp, is_new = await self.add_by_url(line)
                if is_new:
                    added += 1
                else:
                    skipped += 1
            except Exception as e:
                errors.append(f"{line}: {str(e)[:100]}")
                skipped += 1

        return {
            "added": added,
            "skipped": skipped,
            "total_lines": len(lines),
            "errors": errors,
        }

    async def delete_marketplace(self, marketplace_id: UUID) -> bool:
        mp = await self.db.get(DimMarketplace, marketplace_id)
        if not mp:
            return False
        await self.db.delete(mp)
        await self.db.commit()
        return True

    async def update_marketplace(
        self,
        marketplace_id: UUID,
        updates: dict,
    ) -> DimMarketplace | None:
        mp = await self.db.get(DimMarketplace, marketplace_id)
        if not mp:
            return None
        for key, value in updates.items():
            if key not in self._UPDATE_KEYS:
                continue
            if not hasattr(mp, key):
                continue
            if key in ("requires_js", "is_active"):
                setattr(mp, key, bool(value))
                continue
            if value is None:
                continue
            setattr(mp, key, value)
        await self.db.commit()
        await self.db.refresh(mp)
        return mp

    async def recalculate_quotas(self, total_pool_size: int = 50_000) -> dict:
        """Distribute product_quota equally among active marketplaces."""
        active_count = await self.db.scalar(
            select(func.count())
            .select_from(DimMarketplace)
            .where(DimMarketplace.is_active.is_(True)),
        )
        if not active_count:
            return {"message": "No active marketplaces", "quota_per_marketplace": 0}

        quota = total_pool_size // int(active_count)
        await self.db.execute(
            update(DimMarketplace)
            .where(DimMarketplace.is_active.is_(True))
            .values(product_quota=quota)
        )
        await self.db.commit()
        return {
            "active_marketplaces": int(active_count),
            "quota_per_marketplace": quota,
            "total_pool_size": total_pool_size,
        }
