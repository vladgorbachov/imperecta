"""Digest generation Celery tasks (v2 migration stubs)."""

import logging

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)
_V2_MSG = "Pending migration to v2 schema"


@celery_app.task
def generate_weekly_digest(user_id: str) -> None:
    _ = user_id
    logger.warning("generate_weekly_digest skipped: %s", _V2_MSG)


@celery_app.task
def generate_daily_digest(user_id: str) -> None:
    _ = user_id
    logger.warning("generate_daily_digest skipped: %s", _V2_MSG)


@celery_app.task
def schedule_weekly_digests() -> None:
    logger.warning("schedule_weekly_digests skipped: %s", _V2_MSG)


@celery_app.task
def schedule_daily_digests() -> None:
    logger.warning("schedule_daily_digests skipped: %s", _V2_MSG)
