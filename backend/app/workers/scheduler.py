"""Celery Beat schedule configuration."""

from celery.schedules import crontab

from app.workers.celery_app import celery_app

# Only the orphan-job reaper and infra periodics are enabled here.
# Discovery and price-scrape tasks remain MANUAL (triggered via API/admin)
# until parsers are validated end-to-end against the v2 schema.
celery_app.conf.beat_schedule = {
    "orphan-job-reaper": {
        "task": "app.workers.reaper_tasks.reap_orphan_jobs",
        "schedule": 300.0,
    },
    "ensure-fact-price-partitions": {
        "task": "ensure_fact_price_partitions",
        "schedule": crontab(hour=0, minute=0),
    },
    "refresh-materialized-views": {
        "task": "refresh_materialized_views",
        "schedule": crontab(minute=0),
    },
    "cleanup-old-data": {
        "task": "cleanup_old_data",
        "schedule": crontab(hour=3, minute=0),
    },
}
