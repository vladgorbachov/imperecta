"""Celery Beat schedule configuration."""

from app.workers.celery_app import celery_app

# All tasks are disabled until parsers are verified against v2 schema.
celery_app.conf.beat_schedule = {}
