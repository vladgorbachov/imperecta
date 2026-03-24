"""Discovery crawler: DimMarketplace → listing pages → DimProduct + FactListing."""

import logging
import time
from dataclasses import dataclass, field
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
    """Result of discovering product URLs on a marketplace.

    Field groups:
    - Mandatory/system: marketplace_id, status, started_at, completed_at
    - Counts: pages_scanned, candidate_urls_found, accepted_urls,
      duplicate_urls, rejected_urls, persisted_listings
    - Technical: job_id, errors, discovery_method
    """

    marketplace_id: UUID
    status: str  # completed, partial, error, no_categories
    started_at: datetime
    completed_at: datetime | None = None

    # Counts
    pages_scanned: int = 0
    candidate_urls_found: int = 0
    accepted_urls: int = 0
    duplicate_urls: int = 0
    rejected_urls: int = 0
    persisted_listings: int = 0

    # Technical
    job_id: UUID | None = None
    errors: list[str] = field(default_factory=list)
    discovery_method: str = "category_crawl"


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
        started_perf = time.perf_counter()
        started_at = datetime.now(timezone.utc)
        errors: list[str] = []
        mp_id = marketplace.id
        domain = (marketplace.domain or "").strip()

        job = ScrapeJob(
            job_type="discovery",
            marketplace_id=mp_id,
            status="running",
            started_at=started_at,
            config={"domain": domain},
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)

        pages_scanned = 0
        candidate_urls_found = 0
        accepted_urls = 0
        duplicate_urls = 0
        rejected_urls = 0
        persisted_listings = 0
        status = "completed"
        completed_at: datetime | None = None

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

            while page_url and remaining > 0 and pages_scanned < 50:
                listing_res = await self.pool.scrape_listing(
                    url=page_url,
                    custom_link_selector=marketplace.custom_product_link_selector,
                    custom_next_page_selector=marketplace.custom_next_page_selector,
                    requires_js=requires_js,
                )
                pages_scanned += 1
                if not listing_res.success:
                    errors.append(listing_res.error or "listing_fetch_failed")
                    break

                candidate_batch = listing_res.product_urls
                candidate_urls_found += len(candidate_batch)

                deduped_batch = [u for u in candidate_batch if u not in seen_urls]
                duplicate_urls += len(candidate_batch) - len(deduped_batch)

                batch = deduped_batch[:remaining]
                accepted_urls += len(batch)
                rejected_urls += max(0, len(deduped_batch) - len(batch))
                for u in batch:
                    seen_urls.add(u)

                if batch:
                    saved = await self._save_product_urls(mp_id, batch)
                    persisted_listings += saved
                    duplicate_urls += max(0, len(batch) - saved)
                    remaining -= saved

                page_url = listing_res.next_page_url
                if not batch and not page_url:
                    break

            if errors and persisted_listings > 0:
                status = "partial"
            elif errors:
                status = "error"
            elif candidate_urls_found == 0:
                status = "no_categories"
            else:
                status = "completed"

            completed_at = datetime.now(timezone.utc)
            job.status = "failed" if status == "error" else "completed"
            job.completed_at = completed_at
            job.duration_ms = int((time.perf_counter() - started_perf) * 1000)
            job.total_listings = candidate_urls_found
            job.successful = persisted_listings
            job.failed = len(errors)
            job.config = {
                "domain": domain,
                "pages_scanned": pages_scanned,
                "candidate_urls_found": candidate_urls_found,
                "accepted_urls": accepted_urls,
                "duplicate_urls": duplicate_urls,
                "rejected_urls": rejected_urls,
                "discovery_method": "category_crawl",
            }

            marketplace.last_discovery_at = completed_at
            marketplace.last_discovery_status = "failed" if status == "error" else status
            marketplace.last_discovery_products_found = persisted_listings

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
            status = "error"
            completed_at = datetime.now(timezone.utc)
            job.status = "failed"
            job.completed_at = completed_at
            job.duration_ms = int((time.perf_counter() - started_perf) * 1000)
            job.total_listings = candidate_urls_found
            job.successful = persisted_listings
            job.failed = len(errors)
            job.config = {
                "domain": domain,
                "pages_scanned": pages_scanned,
                "candidate_urls_found": candidate_urls_found,
                "accepted_urls": accepted_urls,
                "duplicate_urls": duplicate_urls,
                "rejected_urls": rejected_urls,
                "discovery_method": "category_crawl",
            }
            marketplace.last_discovery_status = "failed"
            try:
                await self.db.commit()
            except Exception:
                await self.db.rollback()

        return DiscoveryResult(
            marketplace_id=mp_id,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            pages_scanned=pages_scanned,
            candidate_urls_found=candidate_urls_found,
            accepted_urls=accepted_urls,
            duplicate_urls=duplicate_urls,
            rejected_urls=rejected_urls,
            persisted_listings=persisted_listings,
            job_id=job.id,
            errors=errors,
            discovery_method="category_crawl",
        )
