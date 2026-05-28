# Backend Full Audit Report (Read-only Snapshot)

Updated: 2026-05-28

## 1) Overview

Backend is a modular FastAPI application under `backend/app/modules/*` with SQLAlchemy models in `backend/app/models/*` and Celery workers in `backend/app/workers/*`.

## 2) Entrypoint and routers

`backend/app/main.py` mounts routers under `/api` for:

- core admin/auth/telegram
- admin parsing
- marketplaces
- product pool
- market data
- dashboard
- user products/import
- analytics
- digests
- AI analyst

Startup executes migration + bootstrap flow and initializes webhook setup.

## 3) Database and migrations

Alembic versions present: `001` to `011`.

Latest additions:

- `010_discovery_universal_columns`
- `011_dedup_and_listing_lifecycle`

Version metadata is stored in `alembic_meta.alembic_version`.

## 4) Worker and scheduling

`backend/app/workers/celery_app.py` includes task modules:

- scraper
- alerts
- digests
- market_data
- cleanup
- maintenance

`backend/app/workers/scheduler.py` currently sets:

- `celery_app.conf.beat_schedule = {}`

This means periodic jobs are disabled by default in code.

## 5) Scraper/runtime notes

Current parser stack is in `modules/scraper` and uses:

- explicit orchestration tasks
- robust fetch+extract fallback
- strict persistence constraints for `fact_price`
- scrape status and lifecycle tracking on listings/logs

## 6) Config and safety

`backend/app/config.py` enforces/normalizes critical settings:

- required DB and Redis connection strings
- Telegram webhook secret requirement when bot token is configured
- DATABASE_URL normalization for async SQLAlchemy

## 7) Key files reviewed

- `backend/app/main.py`
- `backend/app/config.py`
- `backend/app/workers/celery_app.py`
- `backend/app/workers/scheduler.py`
- `backend/alembic/env.py`
- `backend/alembic/versions/*.py`

## 8) Current conclusion

Backend architecture is aligned around v2 star-schema models, modular domain boundaries, parser/admin operational controls, and guarded task execution (with disabled periodic beat schedule by default).
