"""Celery application configuration."""

import ssl

from celery import Celery

from app.config import Settings

settings = Settings()

# Upstash Redis (rediss://) requires ssl_cert_reqs for both broker and result backend
_broker_options: dict = {}
if settings.redis_url.startswith("rediss://"):
    _broker_options = {
        "broker_use_ssl": {"ssl_cert_reqs": ssl.CERT_NONE},
        "redis_backend_use_ssl": {"ssl_cert_reqs": ssl.CERT_NONE},
        "result_backend_transport_options": {"global_keyprefix": "imperecta:"},
    }

celery_app = Celery(
    "imperecta",
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
    broker_connection_retry_on_startup=True,
    **_broker_options,
)

# Load beat schedule from scheduler module
from app.workers import scheduler  # noqa: F401, E402
