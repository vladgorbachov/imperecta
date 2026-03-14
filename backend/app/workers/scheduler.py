"""Celery Beat schedule configuration."""

from celery.schedules import crontab

from app.workers.celery_app import celery_app

celery_app.conf.beat_schedule = {
    "scrape-all-every-6h": {
        "task": "scrape_all",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    "weekly-digests": {
        "task": "app.workers.digest_tasks.schedule_weekly_digests",
        "schedule": crontab(minute=0, hour=18, day_of_week=5),
    },
    "daily-digests": {
        "task": "app.workers.digest_tasks.schedule_daily_digests",
        "schedule": crontab(minute=0, hour=8),
    },
    "cleanup-old-data-weekly": {
        "task": "cleanup_old_data",
        "schedule": crontab(minute=0, hour=4, day_of_week=0),
    },
    "ingest-market-data": {
        "task": "ingest_market_data",
        "schedule": crontab(minute=0, hour="*/2"),
    },
}
