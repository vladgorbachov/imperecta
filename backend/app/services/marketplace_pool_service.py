"""
Marketplace pool management. No hardcoded marketplaces.
All marketplaces come from admin input (URL or file import).
"""

import csv
import io
import logging
from urllib.parse import urlparse

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_marketplace import AdminMarketplace

logger = logging.getLogger(__name__)

TOTAL_POOL_QUOTA = 50_000  # Max products across all marketplaces


class MarketplacePoolService:
    def __init__(self, db: AsyncSession):
        self.db = db

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

    @staticmethod
    def _extract_domain(base_url: str) -> str:
        parsed = urlparse(base_url)
        domain = (parsed.netloc or "").strip().lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain

    @staticmethod
    def _marketplace_id_from_domain(domain: str) -> str:
        return domain.replace(".", "_").replace("-", "_")

    @staticmethod
    def _detect_country_from_domain(domain: str) -> str | None:
        tld = domain.split(".")[-1].lower() if "." in domain else ""
        tld_to_country = {
            "ua": "UA",
            "pl": "PL",
            "de": "DE",
            "ro": "RO",
        }
        return tld_to_country.get(tld)

    @staticmethod
    def _region_for_country(country: str | None) -> str:
        if country in {"RU", "KZ", "BY", "UA"}:
            return "cis"
        return "other"

    async def _fetch_title(self, base_url: str, domain: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                response = await client.get(base_url)
            response.raise_for_status()
            html = response.text or ""
            start = html.lower().find("<title>")
            end = html.lower().find("</title>") if start != -1 else -1
            if start != -1 and end != -1 and end > start:
                title = html[start + 7 : end].strip()
                if title:
                    return title[:100]
        except Exception as exc:
            logger.info("Failed to fetch title for %s: %s", base_url, exc)
        return domain[:100]

    async def add_by_url(self, url: str) -> AdminMarketplace:
        """
        Add marketplace by URL. Auto-extract domain, name, country.

        Steps:
        1. Normalize URL (ensure https://, strip path)
        2. Extract domain via urlparse
        3. Check uniqueness by domain
        4. Determine country from TLD (.ua→UA, .pl→PL, .de→DE, .ro→RO, .com→None)
        5. Try fetch page <title> via httpx (timeout 10s) → use as name
        6. If fetch fails → use domain as name
        7. INSERT with is_active=True
        8. Recalculate quotas for ALL active marketplaces
        9. Return created marketplace
        """
        base_url = self._normalize_url(url)
        domain = self._extract_domain(base_url)
        if not domain:
            raise ValueError("Invalid URL: could not extract domain")

        existing = await self.db.execute(
            select(AdminMarketplace).where(AdminMarketplace.domain == domain)
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Marketplace domain already exists: {domain}")

        country = self._detect_country_from_domain(domain)
        region = self._region_for_country(country)
        name = await self._fetch_title(base_url, domain)

        marketplace = AdminMarketplace(
            marketplace_id=self._marketplace_id_from_domain(domain),
            name=name,
            domain=domain,
            base_url=base_url,
            country=country or "XX",
            region=region,
            currency="USD",
            scraper_type="universal",
            is_active=True,
        )
        self.db.add(marketplace)
        await self.db.flush()
        await self.recalculate_all_quotas()
        await self.db.refresh(marketplace)
        return marketplace

    async def import_from_txt(self, content: str) -> dict:
        """
        Import from .txt content (one URL per line).
        Returns: {"added": N, "skipped": N, "errors": [...]}
        Skip blank lines, comments (#), duplicates.
        """
        added = 0
        skipped = 0
        errors: list[str] = []
        seen: set[str] = set()

        for line_no, line in enumerate(content.splitlines(), start=1):
            raw = line.strip()
            if not raw or raw.startswith("#"):
                skipped += 1
                continue
            try:
                normalized = self._normalize_url(raw)
            except ValueError as exc:
                errors.append(f"line {line_no}: {exc}")
                continue
            if normalized in seen:
                skipped += 1
                continue
            seen.add(normalized)
            try:
                await self.add_by_url(normalized)
                added += 1
            except ValueError:
                skipped += 1
            except Exception as exc:
                errors.append(f"line {line_no}: {exc}")

        return {"added": added, "skipped": skipped, "errors": errors}

    async def import_from_csv(self, content: str) -> dict:
        """
        Import from .csv content. Looks for 'url' column header.
        If no header → treats first column as URL.
        Returns: {"added": N, "skipped": N, "errors": [...]}
        """
        added = 0
        skipped = 0
        errors: list[str] = []
        seen: set[str] = set()

        stream = io.StringIO(content)
        reader = csv.reader(stream)
        rows = list(reader)
        if not rows:
            return {"added": 0, "skipped": 0, "errors": []}

        first_row = [cell.strip().lower() for cell in rows[0]]
        has_url_header = "url" in first_row
        url_values: list[tuple[int, str]] = []

        if has_url_header:
            url_idx = first_row.index("url")
            for idx, row in enumerate(rows[1:], start=2):
                value = row[url_idx].strip() if len(row) > url_idx else ""
                url_values.append((idx, value))
        else:
            for idx, row in enumerate(rows, start=1):
                value = row[0].strip() if row else ""
                url_values.append((idx, value))

        for line_no, raw in url_values:
            if not raw or raw.startswith("#"):
                skipped += 1
                continue
            try:
                normalized = self._normalize_url(raw)
            except ValueError as exc:
                errors.append(f"line {line_no}: {exc}")
                continue
            if normalized in seen:
                skipped += 1
                continue
            seen.add(normalized)
            try:
                await self.add_by_url(normalized)
                added += 1
            except ValueError:
                skipped += 1
            except Exception as exc:
                errors.append(f"line {line_no}: {exc}")

        return {"added": added, "skipped": skipped, "errors": errors}

    async def recalculate_all_quotas(self):
        """
        Set product_quota = TOTAL_POOL_QUOTA / active_count for every active marketplace.
        Called after add/delete/activate/deactivate.
        """
        active_count = await self.db.scalar(
            select(func.count()).where(AdminMarketplace.is_active.is_(True))
        )
        if not active_count:
            return
        quota_per = TOTAL_POOL_QUOTA // active_count
        await self.db.execute(
            update(AdminMarketplace)
            .where(AdminMarketplace.is_active.is_(True))
            .values(product_quota=quota_per)
        )
        await self.db.commit()

    async def list_all(self, is_active: bool | None = None) -> list[AdminMarketplace]:
        """List marketplaces with optional active filter."""
        stmt = select(AdminMarketplace)
        if is_active is not None:
            stmt = stmt.where(AdminMarketplace.is_active.is_(is_active))
        result = await self.db.execute(stmt.order_by(AdminMarketplace.name.asc()))
        return list(result.scalars().all())

    async def delete_marketplace(self, marketplace_id: int):
        """Delete marketplace. CASCADE deletes its global_products. Recalculate quotas."""
        entity = await self.db.get(AdminMarketplace, marketplace_id)
        if entity is None:
            raise ValueError("Marketplace not found")
        await self.db.delete(entity)
        await self.db.flush()
        await self.recalculate_all_quotas()

    async def update_marketplace(self, marketplace_id: int, **kwargs) -> AdminMarketplace:
        """Update marketplace fields. Recalculate quotas if is_active changed."""
        entity = await self.db.get(AdminMarketplace, marketplace_id)
        if entity is None:
            raise ValueError("Marketplace not found")

        is_active_before = bool(entity.is_active)
        for key, value in kwargs.items():
            if hasattr(entity, key) and value is not None:
                setattr(entity, key, value)

        await self.db.flush()
        if bool(entity.is_active) != is_active_before:
            await self.recalculate_all_quotas()
        else:
            await self.db.commit()
        await self.db.refresh(entity)
        return entity
