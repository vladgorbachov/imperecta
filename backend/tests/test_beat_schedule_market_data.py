"""Celery beat schedule includes market-data ingest tasks."""

from app.workers.scheduler import celery_app


def test_beat_schedule_includes_market_data_ingest_tasks() -> None:
    """Beat references existing ingest task names unchanged."""
    schedule = celery_app.conf.beat_schedule
    assert "ensure-fact-price-partitions" not in schedule
    assert "refresh-materialized-views" not in schedule
    assert "ingest-market-data" in schedule
    assert "ingest-commodities" in schedule
    assert schedule["ingest-market-data"]["task"] == "ingest_market_data"
    assert schedule["ingest-commodities"]["task"] == "ingest_commodities"
