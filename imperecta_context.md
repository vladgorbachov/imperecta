# Imperecta Context (Current State)

## Snapshot (2026-05-28)

- Deployment model:
  - Backend + workers on Railway
  - PostgreSQL on Supabase
  - Redis on Upstash
  - Frontend on Cloudflare Pages
- Backend entrypoint `backend/app/main.py` runs:
  1. `alembic upgrade head`
  2. superuser bootstrap
  3. ORM safety `create_all`
  4. Telegram webhook setup in background

## Current focus areas in product

- Admin Data Collection control plane (`/api/admin/parsing/*`):
  - run full pipeline test
  - active job state
  - live feed of steps
  - detailed user and marketplace diagnostics
- Admin UI (`frontend/src/pages/AdminPage.tsx`) now has tabs:
  - `Market Overview`
  - `Data Collection`
  - `Users Management`

## Parser pipeline (actual runtime)

- Runtime path:
  - `tasks -> discovery/service -> scraper_pool -> extractors`
- `ScraperPool` is the fetch+extract facade.
- Worker persistence path is sync-ORM safe:
  - Celery path uses `sync_session_factory`
  - async scraping call is bridged through worker event-loop helper
- Beat schedule is intentionally disabled:
  - `backend/app/workers/scheduler.py` sets `celery_app.conf.beat_schedule = {}`

## Migration status

- Repository contains migrations `001` through `011`.
- Latest chain extension:
  - `010_discovery_universal_columns`
  - `011_dedup_and_listing_lifecycle`
- `011` introduces:
  - `fact_listing.is_active`
  - `fact_listing.last_price_changed_at`
  - `scrape_logs` CHECK including `no_change`

## Data rules enforced in code

- No fake fallback values for critical scrape fields.
- `fact_price` write requires valid name, price, and currency.
- URL-level dedup is based on `fact_listing.url_hash`.
- Listing state tracks lifecycle and repeated failures.

## Frontend stack

- React 19 + TypeScript + Vite 6
- React Router 7
- TanStack Query 5
- Tailwind 4 + shadcn/ui

## Backend stack

- Python 3.12 + FastAPI
- SQLAlchemy 2 + Alembic
- Celery + Redis

## Source-of-truth docs

- `Imperecta_Cursor_Project_Description.md`
- `Imperecta_Full_Development_Context.md`
- `DB_Supabase.md`
- `parsers_audit.md`
- `backend_full_audit_report.md`
