# Parsers Audit — Imperecta

Updated: 2026-05-28

## 1) Scope

This file documents the current parser/discovery stack in backend runtime:

- `backend/app/modules/scraper/*`
- related admin APIs and worker orchestration
- database write behavior for listing and price facts

## 2) Runtime pipeline

Canonical flow:

1. API trigger (admin parsing/scraper endpoints)
2. Celery task orchestration in `modules/scraper/tasks.py`
3. Discovery and scrape service logic (`discovery.py`, `service.py`)
4. Fetch+extract via `scraper_pool.py` and `extractors.py`
5. Persistence into `fact_listing`, `fact_price`, `scrape_logs`, `scrape_jobs`

## 3) Fetch and extraction behavior

Fetch layer order is adaptive:

- Decodo
- httpx
- Playwright

Extraction combines multiple strategies:

- JSON-LD
- meta tags
- selector-driven extraction
- auto-detection heuristics

## 4) Persistence guarantees

Current persistence path enforces:

- no fake fallback values for critical fields
- `fact_price` is written only when data passes quality gate
- listing status/error counters are updated deterministically
- each scrape attempt produces a `scrape_logs` record when listing exists

## 5) DB and migrations relevant to parser

Parser-critical migrations now include:

- `005_scrape_logs_technical_error`
- `006_scrape_logs_status_length`
- `010_discovery_universal_columns`
- `011_dedup_and_listing_lifecycle`

`011` currently introduces:

- `fact_listing.is_active`
- `fact_listing.last_price_changed_at`
- `scrape_logs` CHECK with `no_change`

## 6) Worker strategy

- Celery app configured in `backend/app/workers/celery_app.py`
- Scheduler currently disabled (`beat_schedule = {}`)
- parser jobs are expected to be run intentionally (manual/API-triggered) during controlled operation

## 7) Observability and admin

The parser-admin contour provides:

- full pipeline run trigger
- active job state
- step live feed
- historical test runs
- detailed user/marketplace diagnostics

Frontend admin monitoring is implemented in `frontend/src/pages/AdminPage.tsx`.

## 8) Source files

- `backend/app/modules/scraper/api.py`
- `backend/app/modules/scraper/tasks.py`
- `backend/app/modules/scraper/discovery.py`
- `backend/app/modules/scraper/service.py`
- `backend/app/modules/scraper/scraper_pool.py`
- `backend/app/modules/scraper/extractors.py`
- `backend/alembic/versions/010_discovery_universal_columns.py`
- `backend/alembic/versions/011_dedup_and_listing_lifecycle.py`
