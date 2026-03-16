"""Product pool API contract tests."""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.database import async_session_maker
from app.models import AdminMarketplace, GlobalProduct


async def _seed_marketplace(domain: str, name: str) -> AdminMarketplace:
    async with async_session_maker() as session:
        marketplace = AdminMarketplace(
            marketplace_id=f"pool_{uuid4().hex[:10]}",
            name=name,
            domain=domain,
            base_url=f"https://{domain}",
            country="XX",
            region="other",
            currency="USD",
            scraper_type="universal",
            is_active=True,
        )
        session.add(marketplace)
        await session.commit()
        await session.refresh(marketplace)
        return marketplace


async def _cleanup_marketplace(marketplace_id: int) -> None:
    async with async_session_maker() as session:
        await session.execute(delete(GlobalProduct).where(GlobalProduct.marketplace_id == marketplace_id))
        await session.execute(delete(AdminMarketplace).where(AdminMarketplace.id == marketplace_id))
        await session.commit()


@pytest.mark.asyncio
async def test_list_products_default(client, auth_headers):
    """GET /api/pool/products returns paginated payload."""
    resp = await client.get("/api/pool/products", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data


@pytest.mark.asyncio
async def test_list_products_sort_gainers(client, auth_headers):
    """Gainers should be ordered by price_change_pct_24h DESC."""
    marketplace = await _seed_marketplace("gainers.example", "Gainers")
    try:
        async with async_session_maker() as session:
            for idx, pct in enumerate([Decimal("9.1"), Decimal("2.5"), Decimal("0.3")]):
                url = f"https://gainers.example/product-{idx}"
                session.add(
                    GlobalProduct(
                        marketplace_id=marketplace.id,
                        url=url,
                        url_hash=GlobalProduct.compute_url_hash(url),
                        title=f"Gainer {idx}",
                        current_price=Decimal("100"),
                        price_change_pct_24h=pct,
                        status="active",
                    )
                )
            await session.commit()

        resp = await client.get(
            "/api/pool/products",
            params={"sort": "gainers", "marketplace_id": marketplace.id, "limit": 10},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        values = [item["price_change_pct_24h"] for item in items]
        assert values == sorted(values, reverse=True)
    finally:
        await _cleanup_marketplace(marketplace.id)


@pytest.mark.asyncio
async def test_list_products_search(client, auth_headers):
    """Search should filter by product title with ILIKE."""
    marker = f"phone-{uuid4().hex[:6]}"
    marketplace = await _seed_marketplace("search.example", "Search")
    try:
        async with async_session_maker() as session:
            url1 = f"https://search.example/{marker}"
            url2 = "https://search.example/other-item"
            session.add(
                GlobalProduct(
                    marketplace_id=marketplace.id,
                    url=url1,
                    url_hash=GlobalProduct.compute_url_hash(url1),
                    title=f"Super {marker}",
                    current_price=Decimal("10"),
                    status="active",
                )
            )
            session.add(
                GlobalProduct(
                    marketplace_id=marketplace.id,
                    url=url2,
                    url_hash=GlobalProduct.compute_url_hash(url2),
                    title="Another product",
                    current_price=Decimal("20"),
                    status="active",
                )
            )
            await session.commit()

        resp = await client.get(
            "/api/pool/products",
            params={"search": "phone", "marketplace_id": marketplace.id, "limit": 50},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any("phone" in (item.get("title") or "").lower() for item in data["items"])
    finally:
        await _cleanup_marketplace(marketplace.id)


@pytest.mark.asyncio
async def test_marketplace_stats(client, auth_headers):
    """Marketplace stats endpoint should return grouped counts."""
    marketplace = await _seed_marketplace("stats.example", "Stats")
    try:
        async with async_session_maker() as session:
            for idx in range(2):
                url = f"https://stats.example/p-{idx}"
                session.add(
                    GlobalProduct(
                        marketplace_id=marketplace.id,
                        url=url,
                        url_hash=GlobalProduct.compute_url_hash(url),
                        title=f"Stat {idx}",
                        current_price=Decimal("50"),
                        status="active",
                    )
                )
            await session.commit()

        resp = await client.get("/api/pool/marketplace-stats", headers=auth_headers)
        assert resp.status_code == 200
        rows = resp.json()
        row = next((r for r in rows if r["marketplace_domain"] == "stats.example"), None)
        assert row is not None
        assert row["product_count"] >= 2
    finally:
        await _cleanup_marketplace(marketplace.id)


@pytest.mark.asyncio
async def test_overview_uses_pool(client, auth_headers):
    """Markets overview should now read from global_products pool."""
    marker = f"overview-{uuid4().hex[:6]}"
    marketplace = await _seed_marketplace("overview.example", "Overview")
    try:
        async with async_session_maker() as session:
            url = f"https://overview.example/{marker}"
            session.add(
                GlobalProduct(
                    marketplace_id=marketplace.id,
                    url=url,
                    url_hash=GlobalProduct.compute_url_hash(url),
                    title=marker,
                    image_url="https://overview.example/image.jpg",
                    current_price=Decimal("88.5"),
                    price_change_pct_24h=Decimal("1.2"),
                    status="active",
                )
            )
            await session.commit()

        resp = await client.get(
            "/api/markets/overview",
            params={"search": marker, "marketplace_id": marketplace.id, "limit": 20, "offset": 0},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data and "total" in data
        assert any((item.get("title") == marker and item.get("url")) for item in data["items"])
    finally:
        await _cleanup_marketplace(marketplace.id)
