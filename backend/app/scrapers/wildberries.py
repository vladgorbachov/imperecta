"""Wildberries scraper using card API (no Playwright)."""

import re
from decimal import Decimal

import httpx

from app.scrapers.base import AbstractScraper, ScrapedData


def _extract_article_id(url: str) -> str | None:
    """Extract article_id (nm) from WB product URL."""
    match = re.search(r"/catalog/(\d+)/", url)
    if match:
        return match.group(1)
    match = re.search(r"/(\d+)\.html", url)
    if match:
        return match.group(1)
    return None


class WildberriesScraper(AbstractScraper):
    """Wildberries scraper using card.wb.ru API."""

    API_URL = "https://card.wb.ru/cards/v2/detail"
    DEFAULT_PARAMS = {
        "appType": "1",
        "curr": "rub",
        "dest": "-1257786",
    }

    async def _scrape_impl(self, url: str) -> ScrapedData:
        """Fetch product data from WB card API."""
        article_id = _extract_article_id(url)
        if not article_id:
            raise ValueError("Could not extract article_id from Wildberries URL")

        params = {**self.DEFAULT_PARAMS, "nm": article_id}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(self.API_URL, params=params, headers=headers)

        if response.status_code != 200:
            raise ValueError(f"API returned {response.status_code}")

        data = response.json()
        products = data.get("data", {}).get("products", [])
        if not products:
            raise ValueError("Product not found in API response")

        product = products[0]

        sale_price = product.get("salePriceU")
        price_u = product.get("priceU")
        price = Decimal(sale_price) / 100 if sale_price is not None else None
        old_price = Decimal(price_u) / 100 if price_u and price_u != sale_price else None

        if price is None:
            raise ValueError("Could not extract price from API")

        sizes = product.get("sizes", [])
        in_stock = False
        for s in sizes:
            for st in s.get("stocks", []):
                if st.get("qty", 0) > 0:
                    in_stock = True
                    break
        if not sizes:
            in_stock = True

        sale = product.get("sale")
        promo_label = str(sale) if sale else None

        name = product.get("name")

        return ScrapedData(
            price=price,
            old_price=old_price,
            promo_label=promo_label,
            in_stock=in_stock,
            product_name=name,
        )
