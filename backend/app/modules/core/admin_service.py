"""Admin service: superuser creation and utilities."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.entitlements.plan import UserPlan
from app.models.core import User
from app.modules.core.auth.service import hash_password

logger = logging.getLogger(__name__)


async def ensure_superuser(db: AsyncSession) -> None:
    """Create bootstrap superuser from environment if none exists."""
    settings = Settings()
    admin_email = (settings.bootstrap_admin_email or "").strip().lower()
    admin_password = settings.bootstrap_admin_password or ""
    if not admin_email or not admin_password:
        logger.info("Bootstrap admin credentials are not configured; skipping superuser bootstrap.")
        return

    result = await db.execute(select(User).where(User.is_superuser.is_(True)))
    existing = result.scalar_one_or_none()
    if existing:
        logger.info("Superuser already exists: %s", existing.email)
        return

    admin_name = (settings.bootstrap_admin_name or "").strip()
    admin_language = (settings.bootstrap_admin_language or "").strip()
    raw_plan = (settings.bootstrap_admin_plan or "").strip().lower()
    if not admin_name or not admin_language or not raw_plan:
        logger.error(
            "BOOTSTRAP_ADMIN_NAME, BOOTSTRAP_ADMIN_LANGUAGE, and BOOTSTRAP_ADMIN_PLAN "
            "must be set when bootstrap admin credentials are provided."
        )
        return
    try:
        admin_plan = UserPlan(raw_plan).value
    except ValueError:
        logger.error("Invalid BOOTSTRAP_ADMIN_PLAN: %s", raw_plan)
        return

    superuser = User(
        email=admin_email,
        password_hash=hash_password(admin_password),
        name=admin_name,
        is_superuser=True,
        force_password_change=True,
        plan=admin_plan,
        language=admin_language,
    )
    db.add(superuser)
    await db.commit()
    logger.info("Bootstrap superuser created: %s", admin_email)
