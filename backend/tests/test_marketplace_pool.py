"""Marketplace pool service tests."""

from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.database import async_session_maker
from app.models import AdminMarketplace
from app.services.marketplace_pool_service import MarketplacePoolService


def _unique_domain(suffix: str = "com") -> str:
    return f"mp-{uuid4().hex[:10]}.{suffix}"


async def _cleanup_domains(domains: list[str]) -> None:
    async with async_session_maker() as session:
        await session.execute(
            delete(AdminMarketplace).where(AdminMarketplace.domain.in_(domains))
        )
        await session.commit()


@pytest.mark.asyncio
async def test_add_by_url_extracts_domain():
    """URL with path should be normalized to domain in admin_marketplaces."""
    domain = "rozetka.com.ua"
    await _cleanup_domains([domain])

    async with async_session_maker() as session:
        service = MarketplacePoolService(session)
        mp = await service.add_by_url("https://rozetka.com.ua/some/page")
        assert mp.domain == domain


@pytest.mark.asyncio
async def test_add_by_url_detects_country():
    """Country detection from top-level domain."""
    assert MarketplacePoolService._detect_country_from_domain("site.ua") == "UA"
    assert MarketplacePoolService._detect_country_from_domain("shop.pl") == "PL"
    assert MarketplacePoolService._detect_country_from_domain("example.com") is None


@pytest.mark.asyncio
async def test_add_duplicate_domain_fails():
    """Adding same domain twice should fail."""
    domain = _unique_domain("com")
    await _cleanup_domains([domain])

    async with async_session_maker() as session:
        service = MarketplacePoolService(session)
        await service.add_by_url(f"https://{domain}/a")
        with pytest.raises(ValueError):
            await service.add_by_url(f"https://{domain}/b")


@pytest.mark.asyncio
async def test_import_txt():
    """TXT import should add three marketplaces."""
    d1 = _unique_domain("com")
    d2 = _unique_domain("ua")
    d3 = _unique_domain("pl")
    await _cleanup_domains([d1, d2, d3])

    content = f"https://{d1}\nhttps://{d2}\nhttps://{d3}\n"
    async with async_session_maker() as session:
        service = MarketplacePoolService(session)
        result = await service.import_from_txt(content)
        assert result["added"] == 3


@pytest.mark.asyncio
async def test_import_csv():
    """CSV import with url header should add marketplaces."""
    d1 = _unique_domain("com")
    d2 = _unique_domain("ua")
    await _cleanup_domains([d1, d2])

    content = f"url\nhttps://{d1}\nhttps://{d2}\n"
    async with async_session_maker() as session:
        service = MarketplacePoolService(session)
        result = await service.import_from_csv(content)
        assert result["added"] == 2


@pytest.mark.asyncio
async def test_quota_recalculation():
    """Five active marketplaces should get 10000 quota each."""
    domains = [_unique_domain("com") for _ in range(5)]
    await _cleanup_domains(domains)

    async with async_session_maker() as session:
        for index, domain in enumerate(domains):
            session.add(
                AdminMarketplace(
                    marketplace_id=f"quota_{uuid4().hex[:8]}_{index}",
                    name=domain,
                    domain=domain,
                    base_url=f"https://{domain}",
                    country="XX",
                    region="other",
                    currency="USD",
                    scraper_type="universal",
                    is_active=True,
                )
            )
        await session.commit()

        service = MarketplacePoolService(session)
        await service.recalculate_all_quotas()

        result = await session.execute(
            select(AdminMarketplace).where(AdminMarketplace.domain.in_(domains))
        )
        rows = result.scalars().all()
        assert len(rows) == 5
        assert all(row.product_quota == 10_000 for row in rows)


@pytest.mark.asyncio
async def test_delete_recalculates_quotas():
    """Deleting one marketplace should recalculate quota for remaining active ones."""
    d1 = _unique_domain("com")
    d2 = _unique_domain("ua")
    await _cleanup_domains([d1, d2])

    async with async_session_maker() as session:
        mp1 = AdminMarketplace(
            marketplace_id=f"del_{uuid4().hex[:8]}_1",
            name=d1,
            domain=d1,
            base_url=f"https://{d1}",
            country="XX",
            region="other",
            currency="USD",
            scraper_type="universal",
            is_active=True,
        )
        mp2 = AdminMarketplace(
            marketplace_id=f"del_{uuid4().hex[:8]}_2",
            name=d2,
            domain=d2,
            base_url=f"https://{d2}",
            country="UA",
            region="cis",
            currency="USD",
            scraper_type="universal",
            is_active=True,
        )
        session.add_all([mp1, mp2])
        await session.commit()
        await session.refresh(mp1)
        await session.refresh(mp2)

        service = MarketplacePoolService(session)
        await service.recalculate_all_quotas()
        await service.delete_marketplace(mp1.id)

        result = await session.execute(
            select(AdminMarketplace).where(AdminMarketplace.domain == d2)
        )
        remaining = result.scalar_one()
        assert remaining.product_quota == 50_000
