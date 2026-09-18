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
    # User alert rules: evaluate against fresh fact_price / listing state.
    # Cheap when nothing changed (rule-count bounded); writes via ALERT door.
    "evaluate-price-alerts": {
        "task": "evaluate_price_alerts",
        "schedule": 600.0,
    },
    # Permanent collection: re-scrape stale pool listings (last_checked_at
    # older than 6h). Self-dosing — a tick with no stale listings is a no-op,
    # so the 30-min cadence controls latency, not volume. Direct-HTTP shops
    # only spend their own rate budget (host_throttle); no proxy credits.
    "scrape-stale-pool-products": {
        "task": "scrape_all_pool_products",
        "schedule": crontab(minute="*/30"),
    },
    # Taxonomy enrichment (P13): budget-capped Claude batches — categories →
    # name_en, products → product_type(+en)/title_en, priced-first. Each tick
    # spends at most 1 + PRODUCT_BATCHES_PER_TICK cheap-model calls.
    "taxonomy-enrich": {
        "task": "taxonomy_enrich_tick",
        "schedule": crontab(minute="*/20"),
    },
    # Permanent list-page price collection: 4 stalest category-bearing shops
    # per tick, 20 pages each — the economic backbone (one page ≈ 20-30
    # prices vs 20-30 card fetches). Rotation state lives in Redis.
    "harvest-lists": {
        "task": "harvest_tick",
        "schedule": crontab(minute="*/30"),
    },
}
