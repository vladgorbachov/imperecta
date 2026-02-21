"""Celery application configuration."""

from celery import Celery

from app.config import Settings

settings = Settings()
celery_app = Celery(
    "priceradar",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.workers.scrape_tasks",
        "app.workers.alert_tasks",
        "app.workers.digest_tasks",
    ],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
)

# Load beat schedule from scheduler module
from app.workers import scheduler  # noqa: F401, E402
