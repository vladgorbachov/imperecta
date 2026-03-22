"""Celery Beat schedule configuration."""

from app.workers.celery_app import celery_app

# All tasks are disabled until parsers are verified against v2 schema.
# They will be re-enabled one by one after migration validation.
celery_app.conf.beat_schedule = {
    # "scrape-all-every-2h": {
    #     "task": "scrape_all",
    #     "schedule": crontab(minute=0, hour="*/2"),
    # },
    # "weekly-digests": {
    #     "task": "app.modules.digests.tasks.schedule_weekly_digests",
    #     "schedule": crontab(minute=0, hour=18, day_of_week=5),
    # },
    # "daily-digests": {
    #     "task": "app.modules.digests.tasks.schedule_daily_digests",
    #     "schedule": crontab(minute=0, hour=8),
    # },
    # "cleanup-old-data-weekly": {
    #     "task": "cleanup_old_data",
    #     "schedule": crontab(minute=0, hour=4, day_of_week=0),
    # },
    # "ingest-market-data": {
    #     "task": "ingest_market_data",
    #     "schedule": crontab(minute=0, hour="*/2"),
    # },
    # "ingest-commodities-6h": {
    #     "task": "ingest_commodities",
    #     "schedule": crontab(minute=0, hour="0,6,12,18"),
    # },
    # "discover-all-marketplaces-daily": {
    #     "task": "discover_all_marketplaces",
    #     "schedule": crontab(minute=0, hour=3),
    # },
    # "scrape-pool-products-6h": {
    #     "task": "scrape_all_pool_products",
    #     "schedule": crontab(minute=0, hour="*/6"),
    # },
    # "check-pool-completeness-3h": {
    #     "task": "check_pool_completeness",
    #     "schedule": crontab(minute=30, hour="*/3"),
    # },
    # "refresh-materialized-views": {
    #     "task": "refresh_materialized_views",
    #     "schedule": crontab(minute=15),
    # },
    # "ensure-partitions-monthly": {
    #     "task": "ensure_fact_price_partitions",
    #     "schedule": crontab(minute=0, hour=2, day_of_month=1),
    # },
}
