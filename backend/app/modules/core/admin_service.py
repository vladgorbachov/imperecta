"""Admin service: superuser creation and utilities."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.entitlements.plan import UserPlan
from app.models.core import User
from app.modules.core.auth.service import hash_password

logger = logging.getLogger(__name__)


async def ensure_superuser(db: AsyncSession) -> None:
    """Create default superuser if none exists."""
    result = await db.execute(select(User).where(User.is_superuser.is_(True)))
    existing = result.scalar_one_or_none()
    if existing:
        logger.info("Superuser already exists: %s", existing.email)
        return

    superuser = User(
        email="admin@imperecta.com",
        password_hash=hash_password("admin"),
        name="Administrator",
        is_superuser=True,
        force_password_change=True,
        plan=UserPlan.pro.value,
        language="en",
    )
    db.add(superuser)
    await db.commit()
    logger.info("Default superuser created: admin@imperecta.com / admin")
