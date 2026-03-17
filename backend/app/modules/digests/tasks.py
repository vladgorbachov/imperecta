"""Digest generation Celery tasks."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select

from app.database import async_session_maker
from app.models import User
from app.modules.core.models import UserPlan
from app.modules.digests.service import generate_and_store_digest
from app.workers.celery_app import celery_app


def _run_async(coro):
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task
def generate_weekly_digest(user_id: str) -> None:
    async def _do():
        async with async_session_maker() as session:
            user = (await session.execute(select(User).where(User.id == UUID(user_id)))).scalar_one_or_none()
            if not user:
                return
            now = datetime.now(timezone.utc)
            await generate_and_store_digest(session, user, "weekly", now - timedelta(days=7), now)
            await session.commit()

    _run_async(_do())


@celery_app.task
def generate_daily_digest(user_id: str) -> None:
    async def _do():
        async with async_session_maker() as session:
            user = (await session.execute(select(User).where(User.id == UUID(user_id)))).scalar_one_or_none()
            if not user or user.plan == UserPlan.starter:
                return
            now = datetime.now(timezone.utc)
            await generate_and_store_digest(session, user, "daily", now - timedelta(days=1), now)
            await session.commit()

    _run_async(_do())


@celery_app.task
def schedule_weekly_digests() -> None:
    async def _do():
        async with async_session_maker() as session:
            for row in (await session.execute(select(User.id))).all():
                generate_weekly_digest.delay(str(row[0]))

    _run_async(_do())


@celery_app.task
def schedule_daily_digests() -> None:
    async def _do():
        async with async_session_maker() as session:
            for row in (await session.execute(select(User.id).where(User.plan != UserPlan.starter))).all():
                generate_daily_digest.delay(str(row[0]))

    _run_async(_do())
