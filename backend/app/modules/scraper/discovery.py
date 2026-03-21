"""Discovery crawler: DimMarketplace → listing pages → DimProduct + FactListing."""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_tables import ScrapeJob
from app.models.dimensions import DimMarketplace, DimProduct
from app.models.facts import FactListing
from app.modules.scraper.scraper_pool import ScraperPool

logger = logging.getLogger(__name__)


def _title_from_url(url: str) -> str:
    """Derive placeholder product title from URL path."""
    path = urlparse(url).path.strip("/").split("/")[-1]
    if path:
        return path.replace("-", " ").replace("_", " ")[:500]
    return (url or "product")[:500]


def _normalize_name(name: str) -> str:
    return " ".join((name or "").lower().split())[:500]


@dataclass
class DiscoveryResult:
    marketplace_id: str
    marketplace_domain: str
    status: str
    products_found: int
    products_new: int
    pages_crawled: int
    errors: list[str]
    duration_seconds: int


class DiscoveryCrawler:
    """Crawl marketplace listing pages and persist discovered product URLs."""

    def __init__(self, db: AsyncSession, scraper_pool: ScraperPool):
        self.db = db
        self.pool = scraper_pool

    async def _save_product_urls(self, marketplace_id: UUID, urls: list[str]) -> int:
        """Save discovered URLs. Creates DimProduct + FactListing per new URL."""
        new_count = 0
        for url in urls:
            url_hash = FactListing.compute_url_hash(url)
            exists = await self.db.scalar(select(FactListing.id).where(FactListing.url_hash == url_hash))
            if exists:
                continue

            title = _title_from_url(url) or "product"
            product = DimProduct(
                name=title,
                name_normalized=_normalize_name(title) or "product",
                is_active=True,
            )
            self.db.add(product)
            await self.db.flush()

            listing = FactListing(
                product_id=product.id,
                marketplace_id=marketplace_id,
                external_url=url,
                url_hash=url_hash,
                is_active=True,
            )
            self.db.add(listing)
            new_count += 1

        return new_count

    async def discover(self, marketplace: DimMarketplace) -> DiscoveryResult:
        """Run discovery for one marketplace (ScrapeJob + listing crawl)."""
        started = time.perf_counter()
        errors: list[str] = []
        mp_id = marketplace.id
        domain = (marketplace.domain or "").strip()

        job = ScrapeJob(
            job_type="discovery",
            marketplace_id=mp_id,
            status="running",
            started_at=datetime.now(timezone.utc),
            config={"domain": domain},
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)

        products_found = 0
        products_new = 0
        pages_crawled = 0
        status = "completed"

        try:
            seed_url = (marketplace.base_url or f"https://{domain}").strip()
            if not seed_url.startswith("http"):
                seed_url = f"https://{seed_url}"

            current = await self.db.scalar(
                select(func.count(FactListing.id)).where(FactListing.marketplace_id == mp_id),
            )
            current_count = int(current or 0)
            quota = int(marketplace.product_quota or 0)
            # quota 0 = no explicit cap (large ceiling); quota > 0 = remaining slots
            remaining = max(0, quota - current_count) if quota > 0 else 10_000

            seen_urls: set[str] = set()
            page_url: str | None = seed_url
            requires_js = bool(marketplace.requires_js)

            while page_url and remaining > 0 and pages_crawled < 50:
                listing_res = await self.pool.scrape_listing(
                    url=page_url,
                    custom_link_selector=marketplace.custom_product_link_selector,
                    custom_next_page_selector=marketplace.custom_next_page_selector,
                    requires_js=requires_js,
                )
                pages_crawled += 1
                if not listing_res.success:
                    errors.append(listing_res.error or "listing_fetch_failed")
                    break

                batch = [u for u in listing_res.product_urls if u not in seen_urls][:remaining]
                for u in batch:
                    seen_urls.add(u)
                products_found += len(batch)

                if batch:
                    saved = await self._save_product_urls(mp_id, batch)
                    products_new += saved
                    remaining -= saved

                page_url = listing_res.next_page_url
                if not batch and not page_url:
                    break

            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            job.duration_ms = int((time.perf_counter() - started) * 1000)
            job.total_listings = products_found
            job.successful = products_new

            marketplace.last_discovery_at = datetime.now(timezone.utc)
            marketplace.last_discovery_status = "completed"
            marketplace.last_discovery_products_found = products_new

            pool_count = await self.db.scalar(
                select(func.count(FactListing.id)).where(
                    FactListing.marketplace_id == mp_id,
                    FactListing.is_active.is_(True),
                ),
            )
            marketplace.products_in_pool = int(pool_count or 0)

            await self.db.commit()
        except Exception as exc:
            logger.exception("Discovery failed for %s", mp_id)
            errors.append(str(exc))
            status = "failed"
            job.status = "failed"
            job.completed_at = datetime.now(timezone.utc)
            marketplace.last_discovery_status = "failed"
            try:
                await self.db.commit()
            except Exception:
                await self.db.rollback()

        duration = int(time.perf_counter() - started)
        return DiscoveryResult(
            marketplace_id=str(mp_id),
            marketplace_domain=domain,
            status=status,
            products_found=products_found,
            products_new=products_new,
            pages_crawled=pages_crawled,
            errors=errors,
            duration_seconds=duration,
        )
