# Imperecta — Full Development Context

Updated: 2026-05-28

## 1) Product definition

Imperecta is a SaaS platform for ecommerce monitoring and intelligence:

- marketplace data collection (discovery + scraping)
- competitor and user product tracking
- market widgets (forex/crypto/commodities/fuel)
- alerts and digest workflows
- AI-assisted analysis/chat

## 2) System topology

- Frontend (`frontend/`): React SPA on Cloudflare Pages
- Backend (`backend/`): FastAPI on Railway
- Workers (`backend/app/workers`): Celery worker/beat on Railway
- DB: Supabase PostgreSQL
- Broker: Upstash Redis

## 3) Backend architecture (actual)

Backend is module-first under `backend/app/modules/`:

- `core`
- `admin`
- `marketplaces`
- `scraper`
- `product_pool`
- `user_products`
- `market_data`
- `dashboard`
- `analytics`
- `alerts`
- `digests`
- `ai_analyst`

Legacy flat runtime folders are not the source of truth for current behavior.

## 4) Startup sequence

`backend/app/main.py` lifespan:

1. run Alembic upgrade (`head`)
2. ensure bootstrap superuser
3. run `Base.metadata.create_all` safety net
4. schedule Telegram webhook setup task

All routers are mounted under `/api`.

## 5) Database model

Star-schema pattern plus operational app tables:

- Dimensions: `dim_*`
- Facts: `fact_*`
- App/operational: users, alerts, digests, AI chat, scrape jobs/logs, exports

Important facts:

- `fact_price` is partitioned by `date_id`
- listing identity is URL-based (`fact_listing.url_hash`)
- scrape attempt diagnostics are in `scrape_logs`

## 6) Migration chain status

Repository contains:

- `001_v2_schema`
- `002_v2_additions`
- `003_fix_users_columns`
- `004_fix_real_state`
- `005_scrape_logs_technical_error`
- `006_scrape_logs_status_length`
- `007_fix_migration_deadlock_and_meta`
- `008_fix_alembic_version_length`
- `009_full_v2_schema_rebuild`
- `010_discovery_universal_columns`
- `011_dedup_and_listing_lifecycle`

Latest additions:

- `010`: discovery columns on `dim_marketplace`
- `011`: listing lifecycle columns and `no_change` scrape status

## 7) Scraper/pipeline runtime

Canonical pipeline path:

- `tasks -> discovery/service -> scraper_pool -> extractors`

Behavioral constraints:

- no fake fallback currency/price values
- strict `fact_price` write gate
- explicit listing lifecycle and error counters
- per-attempt scrape logging

## 8) Worker and schedule strategy

- Celery app includes scraper, alerts, digests, market_data, cleanup, maintenance tasks
- Beat schedule is intentionally disabled in code (`{}`) until explicit enablement

## 9) Frontend current state

Primary app routes are defined in `frontend/src/App.tsx`.

Admin area (`/admin`) uses `AdminPage` with tabs:

- Market Overview
- Data Collection
- Users Management

Data Collection tab supports full test pipeline launch and live monitoring.

## 10) Environment and config

Main configuration source: `backend/app/config.py`

- required: `DATABASE_URL`, `REDIS_URL`, auth and app variables
- root `.env` is used for environment loading
- Supabase `postgresql://` URL is normalized to async SQLAlchemy URL format

## 11) Source-of-truth files

- `Imperecta_Cursor_Project_Description.md`
- `imperecta_context.md`
- `DB_Supabase.md`
- `parsers_audit.md`
- `backend_full_audit_report.md`
