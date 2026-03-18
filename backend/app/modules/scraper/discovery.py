"""
Discovery crawler: finds product URLs on marketplace pages.
Fully automatic - no hardcoded category paths.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.marketplaces.models import AdminMarketplace
from app.modules.product_pool.models import GlobalProduct
from app.modules.scraper.models import DiscoveryLog
from app.modules.scraper.scraper_pool import ScraperPool

logger = logging.getLogger(__name__)


@dataclass
class DiscoveryResult:
    marketplace_id: int
    marketplace_domain: str
    status: str
    products_found: int
    products_new: int
    pages_crawled: int
    errors: list[str]
    duration_seconds: int


class DiscoveryCrawler:
    def __init__(self, db: AsyncSession, scraper_pool: ScraperPool):
        self.db = db
        self.pool = scraper_pool

    async def discover(self, marketplace: AdminMarketplace) -> DiscoveryResult:
        started_at = datetime.now(timezone.utc)
        errors: list[str] = []
        pages_crawled = 0
        products_found = 0
        products_new = 0

        log_row = DiscoveryLog(marketplace_id=marketplace.id, status="running")
        self.db.add(log_row)
        await self.db.flush()

        remaining_quota = max(0, (marketplace.product_quota or 0) - (marketplace.products_in_pool or 0))
        if remaining_quota <= 0:
            logger.info(
                "Discovery skip %s: quota=%s, in_pool=%s, remaining=0",
                marketplace.domain,
                marketplace.product_quota,
                marketplace.products_in_pool,
            )
            log_row.status = "completed"
            log_row.completed_at = datetime.now(timezone.utc)
            log_row.duration_seconds = 0
            await self.db.commit()
            return DiscoveryResult(
                marketplace_id=marketplace.id,
                marketplace_domain=marketplace.domain,
                status="completed",
                products_found=0,
                products_new=0,
                pages_crawled=0,
                errors=[],
                duration_seconds=0,
            )

        base_url = marketplace.base_url
        urls: list[str] = []
        requires_js = bool(marketplace.requires_js)
        try:
            sitemap_urls = await self._try_sitemap(
                base_url, limit=remaining_quota, requires_js=requires_js
            )
            urls.extend(sitemap_urls)
        except Exception as exc:
            errors.append(f"sitemap_error: {exc}")

        if len(urls) < max(10, remaining_quota // 10):
            try:
                category_urls = await self._find_category_urls(base_url, requires_js=requires_js)
                if not category_urls and not requires_js:
                    category_urls = await self._find_category_urls(base_url, requires_js=True)
                    if category_urls:
                        marketplace.requires_js = True
                        logger.info("Auto-detected requires_js=True for %s", marketplace.domain)
                for category_url in category_urls:
                    if len(urls) >= remaining_quota:
                        break
                    listing_urls = await self._crawl_listing_pages(
                        listing_url=category_url,
                        marketplace=marketplace,
                        remaining_quota=remaining_quota - len(urls),
                    )
                    pages_crawled += min(50, len(listing_urls) or 1)
                    urls.extend(listing_urls)
            except Exception as exc:
                errors.append(f"category_crawl_error: {exc}")

        deduped_urls = list(dict.fromkeys(urls))[:remaining_quota]
        products_found = len(deduped_urls)

        for product_url in deduped_urls:
            url = (product_url or "").strip()
            if not url or not url.startswith(("http://", "https://")):
                continue
            if len(url) > 2000:
                logger.warning(
                    "Discovery skip: URL too long (%d chars) for %s",
                    len(url),
                    marketplace.domain,
                )
                continue
            url_hash = GlobalProduct.compute_url_hash(url)

            try:
                exists = await self.db.execute(
                    select(GlobalProduct.id).where(GlobalProduct.url_hash == url_hash)
                )
                if exists.scalar_one_or_none() is not None:
                    continue
                self.db.add(
                    GlobalProduct(
                        marketplace_id=marketplace.id,
                        url=url,
                        url_hash=url_hash,
                        status="pending",
                    )
                )
                products_new += 1

                if products_new % 50 == 0:
                    await self.db.commit()

            except Exception as e:
                logger.warning("Error saving URL %s: %s", url[:80], e)
                try:
                    await self.db.rollback()
                except Exception:
                    pass
                continue

        try:
            await self.db.commit()
        except Exception as e:
            logger.error("Final commit failed: %s", e)
            try:
                await self.db.rollback()
            except Exception:
                pass

        await self.db.flush()
        count_result = await self.db.execute(
            select(func.count()).where(GlobalProduct.marketplace_id == marketplace.id)
        )
        marketplace.products_in_pool = int(count_result.scalar() or 0)
        marketplace.last_discovery_at = datetime.now(timezone.utc)

        duration_seconds = int((datetime.now(timezone.utc) - started_at).total_seconds())
        status = "completed" if not errors else ("partial" if products_new > 0 else "failed")

        log_row.status = status
        log_row.pages_crawled = pages_crawled
        log_row.products_found = products_found
        log_row.products_new = products_new
        log_row.errors_count = len(errors)
        log_row.error_message = "; ".join(errors)[:4000] if errors else None
        log_row.duration_seconds = duration_seconds
        log_row.completed_at = datetime.now(timezone.utc)

        await self.db.commit()
        return DiscoveryResult(
            marketplace_id=marketplace.id,
            marketplace_domain=marketplace.domain,
            status=status,
            products_found=products_found,
            products_new=products_new,
            pages_crawled=pages_crawled,
            errors=errors,
            duration_seconds=duration_seconds,
        )

    async def _try_sitemap(
        self, base_url: str, limit: int, requires_js: bool = False
    ) -> list[str]:
        """Fetch sitemap via ScraperPool (Decodo primary) for anti-bot bypass."""
        candidate_paths = ("/sitemap.xml", "/sitemap_index.xml")
        output: list[str] = []
        for path in candidate_paths:
            sitemap_url = urljoin(base_url, path)
            try:
                raw = await self.pool.fetch_html(sitemap_url, requires_js=requires_js)
                if not raw:
                    raw = await self._fetch_sitemap_httpx_fallback(sitemap_url)
                if not raw:
                    continue
                soup = BeautifulSoup(raw, "xml")
                for loc in soup.find_all("loc"):
                    url = (loc.text or "").strip()
                    if self._looks_like_product_url(url):
                        output.append(url)
                        if len(output) >= limit:
                            return list(dict.fromkeys(output))
            except Exception:
                continue
        return list(dict.fromkeys(output))

    async def _fetch_sitemap_httpx_fallback(self, sitemap_url: str) -> str | None:
        """Fallback for sitemap when ScraperPool returns empty (sitemap is often static XML)."""
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                response = await client.get(sitemap_url)
            return response.text if response.status_code < 400 else None
        except Exception:
            return None

    async def _find_category_urls(
        self, base_url: str, requires_js: bool = False
    ) -> list[str]:
        """Fetch homepage via ScraperPool (Decodo primary) to find category links."""
        raw = await self.pool.fetch_html(base_url, requires_js=requires_js)
        if not raw:
            return []
        soup = BeautifulSoup(raw, "html.parser")

        selectors = ["nav a[href]", "header a[href]", "a[href]"]
        collected: list[str] = []
        base_domain = urlparse(base_url).netloc
        for selector in selectors:
            for node in soup.select(selector):
                href = str(node.get("href", "")).strip()
                if not href:
                    continue
                absolute = urljoin(base_url, href)
                parsed = urlparse(absolute)
                if parsed.netloc != base_domain:
                    continue
                path = parsed.path.lower()
                if any(
                    token in path
                    for token in (
                        "/category/",
                        "/c/",
                        "/catalog/",
                        "/shop/",
                        "/products/",
                        "/computer/",
                    )
                ):
                    collected.append(f"{parsed.scheme}://{parsed.netloc}{parsed.path}")
        return list(dict.fromkeys(collected))

    async def _crawl_listing_pages(
        self,
        listing_url: str,
        marketplace: AdminMarketplace,
        remaining_quota: int,
    ) -> list[str]:
        discovered: list[str] = []
        visited: set[str] = set()
        current_url: str | None = listing_url
        max_pages = 50
        page_count = 0
        requires_js = bool(marketplace.requires_js)
        while current_url and current_url not in visited and page_count < max_pages:
            visited.add(current_url)
            page_count += 1
            result = await self.pool.scrape_listing(
                url=current_url,
                custom_link_selector=marketplace.custom_product_link_selector,
                custom_next_page_selector=marketplace.custom_next_page_selector,
                requires_js=requires_js,
            )
            if not result.success and not requires_js and page_count == 1:
                result = await self.pool.scrape_listing(
                    url=current_url,
                    custom_link_selector=marketplace.custom_product_link_selector,
                    custom_next_page_selector=marketplace.custom_next_page_selector,
                    requires_js=True,
                )
                if result.success:
                    marketplace.requires_js = True
                    requires_js = True
                    logger.info("Auto-detected requires_js=True for listing %s", marketplace.domain)
            if not result.success:
                break
            discovered.extend(result.product_urls)
            if len(set(discovered)) >= remaining_quota:
                break
            current_url = result.next_page_url
        return list(dict.fromkeys(discovered))[:remaining_quota]

    @staticmethod
    def _looks_like_product_url(url: str) -> bool:
        parsed = urlparse(url)
        path = parsed.path.lower()
        if any(
            token in path for token in ("/product/", "/products/", "/item/", "/p/", "/tovar/", "/dp/")
        ):
            return True
        if re.search(r"/\d{4,}", path):
            return True
        if ".html" in path:
            return True
        segments = [s for s in path.split("/") if s]
        return len(segments) >= 3
