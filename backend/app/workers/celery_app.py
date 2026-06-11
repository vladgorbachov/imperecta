"""Celery application configuration."""

import ssl

from celery import Celery

from app.config import Settings

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
    broker_transport_options={
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
    "app.workers.cleanup_tasks",
    "app.workers.maintenance_tasks",
    "app.workers.reaper_tasks",
]

# Load beat schedule from scheduler module
from app.workers import scheduler  # noqa: F401, E402
