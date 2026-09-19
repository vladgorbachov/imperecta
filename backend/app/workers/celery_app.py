"""Celery application configuration."""

import os
import ssl

from celery import Celery
from celery.signals import worker_process_init

from app.config import Settings
from app.observability.sentry_init import init_sentry

settings = Settings()

# Upstash Redis (rediss://) requires ssl_cert_reqs for broker
# Result backend disabled to reduce Redis usage (Upstash free tier: 500k req/month)
# All tasks are fire-and-forget; no .get() on AsyncResult used
_broker_options: dict = {}
if settings.redis_url.startswith("rediss://"):
    _broker_options = {
        "broker_use_ssl": {"ssl_cert_reqs": ssl.CERT_NONE},
    }

celery_app = Celery(
    "imperecta",
    broker=settings.redis_url,
    backend=None,  # Disabled to reduce Redis requests (task results not needed)
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    broker_connection_retry=True,
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,
    broker_pool_limit=5,  # Reduce Redis connections for Upstash limits
    # Memory leak containment (2026-09-16 full run: pool processes OOM-killed
    # after ~3h of scraping — soups/render buffers accrete in long-lived
    # prefork children). Recycle a child between tasks after N tasks or when
    # its RSS exceeds the cap; a long discovery task is never interrupted.
    worker_max_tasks_per_child=20,
    worker_max_memory_per_child=400_000,  # KB = ~400MB
    # DB-pressure incident 2026-09-18: default concurrency (=CPU count) once
    # starved the Micro storefront database. After the 2026-09-19 compute
    # upgrade the env pins 6 children; queue priorities below keep bulk
    # enumerations from monopolizing them.
    worker_concurrency=int(os.environ.get("CELERYD_CONCURRENCY", "2")),
    # Queue priorities (2026-09-19): bulk enumerations/discovery must never
    # starve the short periodic ticks (harvest pricing, PDP scrape, matching,
    # enrichment). Redis priorities: 0 = highest; ticks ship at 2, bulk jobs
    # at 8, everything else defaults to 5.
    task_default_priority=5,
    # Bulk work (sitemap enumeration, category discovery) lives on its own
    # queue served by the `celery worker-bulk` service (2026-09-19): on the
    # shared queue strict priority + prefetch (4 x 6 children) starved
    # priority-8 bulk forever once the periodic ticks saturated the pool
    # (434 enumeration shards never received). The main worker consumes
    # only the default queue, so the isolation needs no worker flags.
    task_routes={
        "sitemap_enumerate_marketplace": {"queue": "bulk"},
        "sitemap_enumerate_shard": {"queue": "bulk"},
        "orchestrator_tick": {"queue": "bulk"},
        "discover_all_marketplaces": {"queue": "bulk"},
    },
    broker_transport_options={
        "priority_steps": list(range(10)),
        "queue_order_strategy": "priority",
        "retry_policy": {
            "timeout": 30.0,
            "max_retries": 10,
            "interval_start": 1,
            "interval_step": 2,
            "interval_max": 30,
        }
    },
    **_broker_options,
)
celery_app.conf.include = [
    "app.modules.scraper.tasks",
    "app.workers.market_data_tasks",
    "app.workers.maintenance_tasks",
    "app.workers.reaper_tasks",
    "app.workers.alert_tasks",
    "app.workers.onboarding_tasks",
    "app.workers.harvest_tasks",
    "app.workers.enrichment_tasks",
    "app.workers.matching_tasks",
]

# Load beat schedule from scheduler module
from app.workers import scheduler  # noqa: F401, E402


@worker_process_init.connect
def _init_worker_sentry(**_kwargs: object) -> None:
    """Initialize Sentry in each prefork worker child (not the parent only)."""
    init_sentry(with_celery=True)
