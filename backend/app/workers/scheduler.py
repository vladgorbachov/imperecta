"""Celery Beat schedule configuration."""

from celery.schedules import crontab

from app.workers.celery_app import celery_app

# ingest_market_data: metals (GoldAPI) refresh every 36h, energy (Alpha Vantage) every 24h.
# Cache TTLs are enforced in market_data_service; Beat runs every 2h to catch both windows.
celery_app.conf.beat_schedule = {
    "scrape-all-every-2h": {
        "task": "scrape_all",
        "schedule": crontab(minute=0, hour="*/2"),
    },
    "weekly-digests": {
        "task": "app.modules.digests.tasks.schedule_weekly_digests",
        "schedule": crontab(minute=0, hour=18, day_of_week=5),
    },
    "daily-digests": {
        "task": "app.modules.digests.tasks.schedule_daily_digests",
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
    "ingest-commodities-6h": {
        "task": "ingest_commodities",
        "schedule": crontab(minute=0, hour="0,6,12,18"),
    },
    "discover-all-marketplaces-daily": {
        "task": "discover_all_marketplaces",
        "schedule": crontab(minute=0, hour=3),  # 03:00 UTC daily
    },
    "scrape-pool-products-6h": {
        "task": "scrape_all_pool_products",
        "schedule": crontab(minute=0, hour="*/6"),  # Every 6 hours
    },
    "check-pool-completeness-3h": {
        "task": "check_pool_completeness",
        "schedule": crontab(minute=30, hour="*/3"),  # Every 3 hours at :30
    },
    "refresh-materialized-views": {
        "task": "refresh_materialized_views",
        "schedule": crontab(minute=15),  # Every hour at :15
    },
    "ensure-partitions-monthly": {
        "task": "ensure_fact_price_partitions",
        "schedule": crontab(minute=0, hour=2, day_of_month=1),  # 1st of month, 02:00 UTC
    },
}
