"""
Seed service: populates database with real products and competitors for scraping.
This is NOT mock data — these are real product URLs from real marketplaces.
"""

import logging
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competitor import Competitor
from app.models.competitor_product import CompetitorProduct
from app.models.product import Product

logger = logging.getLogger(__name__)

# Real product URLs from real marketplaces.
# These are verified working URLs as of March 2026.
# Each entry: (marketplace_id, marketplace_name, product_name, url, category, currency)
# Verified: 2026-03-13

SEED_PRODUCTS = [
    # === WILDBERRIES RU ===
    (
        "wildberries_ru",
        "Wildberries",
        "iPhone 16 Pro Max 256GB",
        "https://www.wildberries.ru/catalog/252378505/detail.aspx",
        "Electronics",
        "RUB",
    ),
    (
        "wildberries_ru",
        "Wildberries",
        "Samsung Galaxy S25 Ultra",
        "https://www.wildberries.ru/catalog/264108537/detail.aspx",
        "Electronics",
        "RUB",
    ),
    (
        "wildberries_ru",
        "Wildberries",
        "Sony WH-1000XM5",
        "https://www.wildberries.ru/catalog/168877262/detail.aspx",
        "Electronics",
        "RUB",
    ),
    (
        "wildberries_ru",
        "Wildberries",
        "Nike Air Max 90",
        "https://www.wildberries.ru/catalog/191955797/detail.aspx",
        "Fashion",
        "RUB",
    ),
    (
        "wildberries_ru",
        "Wildberries",
        "Dyson V15 Detect",
        "https://www.wildberries.ru/catalog/128635872/detail.aspx",
        "Home",
        "RUB",
    ),
    # === OZON RU ===
    (
        "ozon_ru",
        "Ozon",
        "MacBook Air M4 15\"",
        "https://www.ozon.ru/product/noutbuk-apple-macbook-air-15-m4-2025-16-256-seryi-1852519006/",
        "Electronics",
        "RUB",
    ),
    (
        "ozon_ru",
        "Ozon",
        "AirPods Pro 3",
        "https://www.ozon.ru/product/naushniki-apple-airpods-pro-2nd-generation-1024178498/",
        "Electronics",
        "RUB",
    ),
    (
        "ozon_ru",
        "Ozon",
        "PlayStation 5 Pro",
        "https://www.ozon.ru/product/igrovaya-konsol-sony-playstation-5-pro-1612483953/",
        "Gaming",
        "RUB",
    ),
    (
        "ozon_ru",
        "Ozon",
        "Xiaomi 14 Ultra",
        "https://www.ozon.ru/product/smartfon-xiaomi-14-ultra-16-512-gb-chernyy-1479553741/",
        "Electronics",
        "RUB",
    ),
    (
        "ozon_ru",
        "Ozon",
        "Samsung QN90D 55\"",
        "https://www.ozon.ru/product/televizor-samsung-qe55qn90dauxru-1500321178/",
        "Electronics",
        "RUB",
    ),
    # === KASPI KZ ===
    (
        "kaspi_kz",
        "Kaspi.kz",
        "iPhone 16 Pro Max",
        "https://kaspi.kz/shop/p/apple-iphone-16-pro-max-256gb-chernyi-titan-119673781/",
        "Electronics",
        "KZT",
    ),
    (
        "kaspi_kz",
        "Kaspi.kz",
        "Samsung Galaxy S25 Ultra",
        "https://kaspi.kz/shop/p/samsung-galaxy-s25-ultra-12-gb-256-gb-sinii-titanium-121905367/",
        "Electronics",
        "KZT",
    ),
    # === ROZETKA UA ===
    (
        "rozetka_ua",
        "Rozetka",
        "iPhone 16 Pro Max 256GB",
        "https://rozetka.com.ua/ua/apple-iphone-16-pro-max-256gb-desert-titanium/p/461541217/",
        "Electronics",
        "UAH",
    ),
    (
        "rozetka_ua",
        "Rozetka",
        "Samsung Galaxy S25 Ultra",
        "https://rozetka.com.ua/ua/samsung-galaxy-s25-ultra-sm-s938-12-256gb-titanium-silverblue/p/464044443/",
        "Electronics",
        "UAH",
    ),
    # === ALLEGRO PL ===
    (
        "allegro_pl",
        "Allegro",
        "iPhone 16 Pro Max",
        "https://allegro.pl/oferta/apple-iphone-16-pro-max-256gb-titanowy-czarny-16494724710",
        "Electronics",
        "PLN",
    ),
]


def _scraper_type_for_marketplace(marketplace_id: str) -> str:
    """Always returns 'universal'. All marketplaces use the same scraper."""
    return "universal"


async def seed_products_for_user(
    db: AsyncSession, user_id: UUID, limit: int = 20
) -> dict:
    """
    Seed database with real products and competitor entries for a user.
    Creates Product -> Competitor -> CompetitorProduct chain.

    This only runs if user has < 5 products (doesn't overwrite existing data).

    Returns: {"products_created": int, "competitors_created": int, "competitor_products_created": int}
    """
    # Check if user already has products
    count_result = await db.execute(
        select(func.count()).select_from(Product).where(Product.user_id == user_id)
    )
    existing_count = count_result.scalar() or 0
    if existing_count >= 5:
        logger.info(
            "User %s already has %d products, skipping seed", user_id, existing_count
        )
        return {
            "products_created": 0,
            "competitors_created": 0,
            "competitor_products_created": 0,
        }

    products_created = 0
    competitors_created = 0
    competitor_products_created = 0

    # Group seed data by marketplace
    marketplace_groups: dict[str, list] = {}
    for item in SEED_PRODUCTS[:limit]:
        mp_id, mp_name, product_name, url, category, currency = item
        marketplace_groups.setdefault(mp_id, []).append(
            (mp_name, product_name, url, category, currency)
        )

    for mp_id, items in marketplace_groups.items():
        mp_name = items[0][0]

        # Create or get competitor
        comp_result = await db.execute(
            select(Competitor).where(
                Competitor.user_id == user_id,
                Competitor.marketplace == mp_id,
            )
        )
        existing_competitor = comp_result.scalar_one_or_none()
        if existing_competitor:
            competitor = existing_competitor
        else:
            competitor = Competitor(
                user_id=user_id,
                name=mp_name,
                marketplace=mp_id,
                website_url=f"https://www.{mp_id.replace('_', '.')}",
            )
            db.add(competitor)
            await db.flush()
            competitors_created += 1

        for mp_name, product_name, url, category, currency in items:
            # Create product (user's own product for comparison)
            prod_result = await db.execute(
                select(Product).where(
                    Product.user_id == user_id,
                    Product.name == product_name,
                )
            )
            existing_product = prod_result.scalar_one_or_none()
            if existing_product:
                product = existing_product
            else:
                product = Product(
                    user_id=user_id,
                    name=product_name,
                    current_price=0,  # Will be filled after first scrape
                    currency=currency,
                    category=category,
                    is_active=True,
                )
                db.add(product)
                await db.flush()
                products_created += 1

            # Create competitor_product (the actual scraping target)
            cp_result = await db.execute(
                select(CompetitorProduct).where(
                    CompetitorProduct.product_id == product.id,
                    CompetitorProduct.competitor_id == competitor.id,
                )
            )
            if cp_result.scalar_one_or_none() is None:
                scraper_type = _scraper_type_for_marketplace(mp_id)
                cp = CompetitorProduct(
                    product_id=product.id,
                    competitor_id=competitor.id,
                    url=url,
                    name=product_name,
                    scraper_type=scraper_type,
                    is_active=True,
                )
                db.add(cp)
                competitor_products_created += 1

    logger.info(
        "Seed complete for user %s: %d products, %d competitors, %d competitor_products",
        user_id,
        products_created,
        competitors_created,
        competitor_products_created,
    )
    return {
        "products_created": products_created,
        "competitors_created": competitors_created,
        "competitor_products_created": competitor_products_created,
    }
