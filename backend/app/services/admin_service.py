"""Admin service: superuser creation and utilities."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.models.user import UserPlan
from app.services.auth_service import hash_password

logger = logging.getLogger(__name__)


async def ensure_superuser(db: AsyncSession) -> None:
    """Create default superuser if none exists. Called on app startup."""
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
        plan=UserPlan.pro,
        language="en",
    )
    db.add(superuser)
    await db.commit()
    logger.info("Default superuser created: admin@imperecta.com / admin")
