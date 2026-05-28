"""Discovery crawler: DimMarketplace → listing pages → DimProduct + FactListing."""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.app_tables import ScrapeJob
from app.models.dimensions import DimMarketplace, DimProduct
from app.models.facts import FactListing
from app.modules.scraper.scraper_pool import ScraperPool

logger = logging.getLogger(__name__)

# Days before category recon is re-run for a marketplace.
CATEGORY_RECON_STALE_DAYS = 7
# Days before sitemap harvest is re-run.
SITEMAP_STALE_DAYS = 3
# Max category URLs to harvest products from per discovery run.
MAX_CATEGORY_URLS_PER_RUN = 60
# Max pages to paginate within a single category URL.
MAX_PAGES_PER_CATEGORY = 50
# Max BFS depth when exploring hub pages for category links.
RECON_BFS_MAX_DEPTH = 3
# Min URLs found via sitemap to consider sitemap harvest successful.
SITEMAP_MIN_USEFUL_URLS = 10


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

    @staticmethod
    def _seed_candidates(seed_url: str) -> list[str]:
        """Generate alternative category/listing entry URLs for marketplaces."""
        parsed = urlparse(seed_url)
        if not parsed.scheme or not parsed.netloc:
            return [seed_url]
        origin = f"{parsed.scheme}://{parsed.netloc}"
        raw_path = (parsed.path or "").strip("/")
        candidates: list[str] = [seed_url]
        if raw_path:
            candidates.append(f"{origin}/{raw_path}")
        fallbacks = (
            "catalog",
            "products",
            "shop",
            "categories",
            "collections",
            "ru/catalog",
            "ua/catalog",
            "bg/catalog",
            "en/catalog",
        )
        for fallback in fallbacks:
            candidates.append(f"{origin}/{fallback}")
        # Preserve order, remove duplicates.
        seen: set[str] = set()
        out: list[str] = []
        for url in candidates:
            if url in seen:
                continue
            seen.add(url)
            out.append(url)
        return out

    async def _save_product_urls(self, marketplace_id: UUID, urls: list[str]) -> int:
        """Save discovered URLs. Creates DimProduct + FactListing per new URL."""
        if not urls:
            return 0

        normalized_urls = [url for url in urls if url]
        hash_by_url = {url: FactListing.compute_url_hash(url) for url in normalized_urls}
        existing_hashes_result = await self.db.execute(
            select(FactListing.url_hash).where(FactListing.url_hash.in_(list(hash_by_url.values()))),
        )
        existing_hashes = {row[0] for row in existing_hashes_result.all() if row[0]}

        new_count = 0
        for url in normalized_urls:
            url_hash = hash_by_url[url]
            if url_hash in existing_hashes:
                continue

            title = _title_from_url(url) or "product"
            product_id = uuid4()
            product = DimProduct(
                id=product_id,
                name=title,
                name_normalized=_normalize_name(title) or "product",
                is_active=True,
            )
            self.db.add(product)

            listing = FactListing(
                product_id=product_id,
                marketplace_id=marketplace_id,
                external_url=url,
                url_hash=url_hash,
                is_active=True,
            )
            self.db.add(listing)
            existing_hashes.add(url_hash)
            new_count += 1

        if new_count > 0:
            await self.db.flush()
        return new_count

    def _should_run_sitemap_harvest(self, marketplace: DimMarketplace) -> bool:
        """Return True if sitemap harvest should run."""
        if marketplace.last_sitemap_harvest_at is None:
            return True
        age = (datetime.now(tz=timezone.utc) - marketplace.last_sitemap_harvest_at).days
        return age >= SITEMAP_STALE_DAYS

    def _should_run_category_recon(self, marketplace: DimMarketplace) -> bool:
        """Return True if category recon should run."""
        if not marketplace.discovered_category_urls:
            return True
        if marketplace.last_category_recon_at is None:
            return True
        age = (datetime.now(tz=timezone.utc) - marketplace.last_category_recon_at).days
        return age >= CATEGORY_RECON_STALE_DAYS

    async def _phase0_sitemap_harvest(self, marketplace: DimMarketplace) -> list[str]:
        """Phase 0: attempt to collect product URLs from XML sitemaps."""
        logger.info(
            "sitemap_harvest_start marketplace_id=%s url=%s",
            marketplace.id,
            marketplace.base_url,
        )
        urls = await self.pool.fetch_sitemap_candidates(marketplace.base_url)
        marketplace.last_sitemap_harvest_at = datetime.now(tz=timezone.utc)
        if urls:
            marketplace.sitemap_url = f"{marketplace.base_url.rstrip('/')}/sitemap.xml"
        await self.db.flush()
        logger.info(
            "sitemap_harvest_done marketplace_id=%s urls_found=%d",
            marketplace.id,
            len(urls),
        )
        return urls

    async def _phase1_category_recon(self, marketplace: DimMarketplace) -> list[str]:
        """Phase 1: BFS traversal to discover category/listing URLs."""
        from collections import deque

        from app.modules.scraper.extractors import classify_page_role, extract_internal_links_all

        logger.info(
            "category_recon_start marketplace_id=%s url=%s",
            marketplace.id,
            marketplace.base_url,
        )
        queue: deque[tuple[str, int]] = deque([(marketplace.base_url, 0)])
        visited: set[str] = {marketplace.base_url}
        listing_urls: list[str] = []
        fallback_seeds = ["/catalog", "/categories", "/shop", "/store", "/all"]

        while queue:
            current_url, depth = queue.popleft()
            if depth > RECON_BFS_MAX_DEPTH:
                continue
            _html, soup = await self.pool.scrape_page_for_analysis(
                current_url,
                static_fetch=True,
            )
            if soup is None:
                continue
            role = classify_page_role(soup, marketplace.base_url)
            logger.debug(
                "recon_page marketplace_id=%s url=%s depth=%d role=%s",
                marketplace.id,
                current_url,
                depth,
                role,
            )
            if role == "listing":
                if current_url != marketplace.base_url:
                    listing_urls.append(current_url)
                if depth < RECON_BFS_MAX_DEPTH:
                    for link in extract_internal_links_all(soup, marketplace.base_url):
                        if link not in visited:
                            visited.add(link)
                            queue.append((link, depth + 1))
            elif role in ("hub", "unknown"):
                for link in extract_internal_links_all(soup, marketplace.base_url):
                    if link not in visited:
                        visited.add(link)
                        queue.append((link, depth + 1))

        if not listing_urls:
            for fallback in fallback_seeds:
                fallback_url = f"{marketplace.base_url.rstrip('/')}{fallback}"
                if fallback_url in visited:
                    continue
                _html, soup = await self.pool.scrape_page_for_analysis(
                    fallback_url,
                    static_fetch=True,
                )
                if soup is None:
                    continue
                role = classify_page_role(soup, marketplace.base_url)
                if role in ("listing", "hub"):
                    listing_urls.append(fallback_url)

        seen: set[str] = set()
        unique: list[str] = []
        for url in listing_urls:
            if url not in seen:
                seen.add(url)
                unique.append(url)

        marketplace.discovered_category_urls = unique
        marketplace.last_category_recon_at = datetime.now(tz=timezone.utc)
        await self.db.flush()
        logger.info(
            "category_recon_done marketplace_id=%s listing_urls_found=%d",
            marketplace.id,
            len(unique),
        )
        return unique

    async def _phase2_product_harvest(
        self,
        marketplace: DimMarketplace,
        category_urls: list[str],
    ) -> int:
        """Phase 2: crawl each category URL, extract product links, save to pool."""
        from app.modules.scraper.extractors import (
            detect_next_page,
            extract_links_from_repeated_structure,
            extract_product_links,
        )

        total_saved = 0
        harvest_targets = category_urls[:MAX_CATEGORY_URLS_PER_RUN]

        for category_url in harvest_targets:
            current_url: str | None = category_url
            page_num = 0
            while current_url and page_num < MAX_PAGES_PER_CATEGORY:
                _html, soup = await self.pool.scrape_page_for_analysis(
                    current_url,
                    static_fetch=True,
                )
                if soup is None:
                    break

                product_urls = extract_links_from_repeated_structure(
                    soup,
                    marketplace.base_url,
                    current_url,
                )
                if not product_urls:
                    product_urls = extract_product_links(soup, marketplace.base_url)
                if product_urls:
                    total_saved += await self._save_product_urls(marketplace.id, product_urls)

                next_page = detect_next_page(soup, current_url)
                current_url = next_page
                page_num += 1
        return total_saved

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
            settings = Settings()
            seed_url = (marketplace.base_url or f"https://{domain}").strip()
            if not seed_url.startswith("http"):
                seed_url = f"https://{seed_url}"
            if marketplace.base_url != seed_url:
                marketplace.base_url = seed_url

            current = await self.db.scalar(
                select(func.count(FactListing.id)).where(FactListing.marketplace_id == mp_id),
            )
            current_count = int(current or 0)
            quota = int(marketplace.product_quota or 0)
            no_quota_limit = max(int(settings.discovery_no_quota_limit or 200000), 1)
            # quota 0 = no explicit cap (large ceiling); quota > 0 = remaining slots
            remaining = max(0, quota - current_count) if quota > 0 else no_quota_limit

            sitemap_product_urls: list[str] = []
            if self._should_run_sitemap_harvest(marketplace):
                sitemap_product_urls = await self._phase0_sitemap_harvest(marketplace)

            products_found = 0
            if len(sitemap_product_urls) >= SITEMAP_MIN_USEFUL_URLS:
                logger.info(
                    "discovery_using_sitemap marketplace_id=%s url_count=%d",
                    marketplace.id,
                    len(sitemap_product_urls),
                )
                candidate_urls_found = len(sitemap_product_urls)
                batch = sitemap_product_urls[:remaining]
                accepted_urls = len(batch)
                rejected_urls = max(0, len(sitemap_product_urls) - len(batch))
                products_found = await self._save_product_urls(marketplace.id, batch)
                persisted_listings = products_found
                duplicate_urls = max(0, len(batch) - products_found)
                remaining = max(0, remaining - products_found)
                pages_scanned = 1 if sitemap_product_urls else 0
            else:
                if self._should_run_category_recon(marketplace):
                    await self._phase1_category_recon(marketplace)

                harvest_urls = [marketplace.base_url] + (marketplace.discovered_category_urls or [])
                candidate_urls_found = len(harvest_urls)
                accepted_urls = min(len(harvest_urls), remaining)
                rejected_urls = max(0, len(harvest_urls) - accepted_urls)
                pages_scanned = accepted_urls
                products_found = await self._phase2_product_harvest(
                    marketplace,
                    harvest_urls[:accepted_urls],
                )
                persisted_listings = products_found
                duplicate_urls = max(0, accepted_urls - products_found)
                remaining = max(0, remaining - products_found)

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
