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
    "pipeline-tick-watchdog": {
        "task": "app.workers.reaper_tasks.revive_stalled_pipeline_ticks",
        "schedule": 60.0,
    },
    "ensure-fact-price-partitions": {
        "task": "ensure_fact_price_partitions",
        "schedule": crontab(hour=0, minute=0),
    },
    "refresh-materialized-views": {
        "task": "refresh_materialized_views",
        "schedule": crontab(minute=0),
    },
    "service-data-retention": {
        "task": "run_service_data_retention",
        "schedule": crontab(minute=15, hour="*/4"),
    },
    # Market-data ingest: keep fact_currency_rate / crypto / commodity snapshots fresh
    # so scrape-day price_eur resolves (forex+crypto every 6h; commodities 4x/day).
    "ingest-market-data": {
        "task": "ingest_market_data",
        "schedule": crontab(minute=5, hour="*/6"),
    },
    "ingest-commodities": {
        "task": "ingest_commodities",
        "schedule": crontab(minute=35, hour="2,8,14,20"),
    },
}
