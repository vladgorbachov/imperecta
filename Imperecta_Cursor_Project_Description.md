# Imperecta — Project Description for Cursor

## Current state (2026-05-28)

Imperecta is an ecommerce intelligence platform with a modular FastAPI backend, React frontend, and a scraping/discovery pipeline backed by Celery workers.

## Architecture

- Backend: `backend/app/modules/*` (domain-based modules)
- Frontend: `frontend/src/*` (React + TypeScript)
- Database: Supabase PostgreSQL (star schema)
- Queue/broker: Upstash Redis
- Compute: Railway services (`backend`, `celery-worker`, `celery-beat`)
- Web app hosting: Cloudflare Pages

## Runtime flow

1. Frontend calls `/api/*` endpoints.
2. FastAPI handles auth, admin, pool, analytics and AI features.
3. Scrape/discovery jobs are executed by Celery tasks.
4. Results are persisted into `dim_*`, `fact_*`, and app tables.

## Backend module map

- `core`: auth, admin core, telegram
- `admin`: parsing administration APIs/services
- `marketplaces`: marketplace management
- `scraper`: discovery, scraping, extractors, worker tasks
- `product_pool`: global pool APIs and stats
- `user_products`: user products/competitors/import
- `market_data`: forex/crypto/commodities/fuel ingestion and APIs
- `dashboard`: KPI/overview aggregations
- `analytics`: forecasts/comparisons
- `alerts`: rules, events, notifications
- `digests`: digest generation and retrieval
- `ai_analyst`: AI chat and orchestration

## Frontend routes (high-level)

- Public: landing, login, register, forgot-password
- Protected: dashboard, products, product details, digests, import, analytics, AI, settings
- Superuser: `/admin`

## Admin UX (current)

`AdminPage` includes three tabs:

- `Market Overview`
- `Data Collection`
- `Users Management`

Data Collection supports launching full pipeline tests and observing live step-level telemetry.

## Migrations and DB

- Alembic files currently extend from `001` to `011`.
- Notable latest revisions:
  - `010_discovery_universal_columns`
  - `011_dedup_and_listing_lifecycle`
- Version metadata is kept in `alembic_meta.alembic_version`.

## Scheduler mode

- Automatic beat scheduling is disabled intentionally:
  - `backend/app/workers/scheduler.py` -> `celery_app.conf.beat_schedule = {}`

## Parser design constraints

- Single canonical scrape path:
  - `tasks -> discovery/service -> scraper_pool -> extractors`
- Persistence is conservative:
  - no fake currency/price fallback
  - strict write gate for `fact_price`
  - URL dedup and listing lifecycle controls

## Tech stack snapshot

- Backend: Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Celery
- Frontend: React 19, TypeScript, Vite 6, React Router 7, TanStack Query 5, Tailwind 4
- E2E: Playwright

## Operational notes

- Environment is driven by root `.env`.
- `DATABASE_URL` and `REDIS_URL` are required.
- Supabase-style `postgresql://` URLs are auto-normalized for async SQLAlchemy.

## Source references

- `backend/app/main.py`
- `backend/app/config.py`
- `backend/app/workers/celery_app.py`
- `backend/app/workers/scheduler.py`
- `backend/alembic/versions/*.py`
- `frontend/src/App.tsx`
- `frontend/src/pages/AdminPage.tsx`
