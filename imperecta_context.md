# Imperecta Context (Current State)

## 0) Snapshot (2026-03-31)

- Description docs aligned: `Imperecta_Cursor_Project_Description.md`, `backend_full_audit_report.md`, `parsers_audit.md`, this file.
- Parser runtime: no `engine.py` under `modules/scraper`; path remains `tasks → discovery/service → scraper_pool → extractors`.
- **Marketplaces:** `MarketplaceService` + `modules/marketplaces/api.py` persist rows in `dim_marketplace` (add-by-url, import, delete, quotas, `requires_js`, logs). **POST `/api/admin/marketplaces/deduplicate`** is still a no-op merge (returns a message). Pool/diagnostics/cleanup: `core/api_admin` + `scraper/api`.
- Celery Beat: `scheduler.py` sets `celery_app.conf.beat_schedule = {}` (no periodic enqueue).

## 0.1) Parser Runtime Update (2026-03-24)

- `backend/app/modules/scraper/engine.py` removed from production runtime.
- Canonical parser path: `tasks -> discovery/service -> scraper_pool -> extractors`.
- `scraper_pool.py` is the single fetch+extract facade for scraping operations.
- `PoolScrapeResult` contract is expanded with quality metadata:
  - `is_partial`, `is_empty`, `fields_extracted`, `fields_missing`.
- `DiscoveryCrawler.discover()` now returns structured `DiscoveryResult` dataclass instead of a dict.
- Persistence path in `service.py` updated:
  - no fallback currency default (`USD` removed),
  - `FactPrice` is skipped when currency is missing,
  - `in_stock` persists extracted value (including `None`),
  - `scrape_logs` now records each attempt (success/failure/technical metadata).
- Beat schedule remains intentionally disabled: `celery_app.conf.beat_schedule = {}`.

---

## 1) Product Summary

Imperecta is a SaaS platform for ecommerce competitive intelligence.  
Core workflows:
- Track competitor prices and stock across marketplaces.
- Build and maintain a global product pool via discovery and scraping.
- Provide market widgets (forex, crypto, commodities, fuel).
- Generate digest reports and alert events with AI assistance.

The system combines a React frontend, FastAPI backend, PostgreSQL (Supabase), and Celery workers.

---

## 2) High-Level Architecture

### Frontend
- Stack: Vite + React + TypeScript.
- Routing: React Router.
- Data fetching: TanStack Query + Axios.
- UI: Tailwind + shadcn/ui components.
- Main areas: dashboard, products, competitors, alerts, digests, import, analytics, AI chat, admin.

### Backend
- Stack: FastAPI + SQLAlchemy 2 (async API) + Celery.
- Pattern: module-based backend under `backend/app/modules/*`.
- API prefix: `/api` for business endpoints.
- Startup responsibilities: schema checks/migrations readiness, `ensure_superuser`, Telegram webhook setup.

### Data & Infra
- PostgreSQL on Supabase.
- Redis for Celery broker/backing queues.
- External APIs: market data providers, scraping providers, AI provider.
- Alembic for schema evolution.

---

## 3) Backend Modules (Domain Map)

- `modules/core`: auth, health, admin core actions, dependency and security integration.
- `modules/marketplaces`: marketplace admin management and operational settings.
- `modules/scraper`: discovery + scraping orchestration and related admin controls.
- `modules/product_pool`: global pool browsing/searching/statistics.
- `modules/user_products`: user-managed products and related operations.
- `modules/market_data`: ingestion and API for forex/crypto/commodities/fuel.
- `modules/dashboard`: KPI and dashboard-facing aggregation.
- `modules/analytics`: product analytics, forecasts, benchmark/comparison.
- `modules/alerts`: alert rules/events and AI-assisted explanation flows.
- `modules/digests`: digest generation/scheduling.
- `modules/ai_analyst`: chat and AI orchestration.

---

## 4) Current Database Model Strategy

### Canonical v2 Model
The project uses a star-schema-style v2 model:
- Dimensions: `dim_date`, `dim_currency`, `dim_country`, `dim_marketplace`, `dim_category`, `dim_brand`, `dim_product`, `dim_seller`.
- Facts: `fact_listing`, `fact_price`, `fact_review`, `fact_stock`, `fact_search_trend`, `fact_currency_rate`, `fact_tariff`, `fact_promo`, `fact_crypto_price`, `fact_commodity_price`, `fact_fuel_price`.
- App tables: `users`, `user_subscriptions`, `user_products`, `alerts`, `alert_events`, `digests`, `ai_chat_sessions`, `ai_chat_messages`, `scrape_jobs`, `scrape_logs`, `api_logs`, `data_exports`.

### Important Notes
- `fact_price` is partitioned by `date_id`.
- Materialized views exist for summary/health reporting and are refreshed by maintenance tasks.
- Alembic versioning is stored in `alembic_meta.alembic_version` (not `public.alembic_version`).

---

## 5) Alembic Migration Chain (Current)

Current chain:
1. `001_v2_schema`
2. `002_v2_additions`
3. `003_fix_users_columns`
4. `004_fix_real_state` (current head)

### Why 003 and 004 exist
- `003_fix_users_columns` adds missing `users` fields with `IF NOT EXISTS` and retries `pg_trgm` extension creation.
- `004_fix_real_state` addresses real-world production drift:
  - Normalizes `users.plan` from enum to `VARCHAR(20)` and applies constraints.
  - Adds/ensures required `users` columns for ORM compatibility.
  - Drops legacy tables/types/sequences.
  - Recreates several app tables with v2-compatible structure when needed.
  - Re-ensures `pg_trgm`.

This migration chain is designed to be robust against partially applied historical states.

---

## 6) Scheduler and Background Processing

- Celery task modules are still registered in the worker.
- `backend/app/workers/scheduler.py` currently sets:
  - `celery_app.conf.beat_schedule = {}`
- This means beat does not auto-trigger periodic tasks in current safe mode.
- Rationale: prevent automatic ingestion/scraping while schema/parser state is being stabilized.

---

## 7) Authentication and User-Side Stability

Key runtime expectation:
- ORM `User` model requires v2 columns like `timezone`, `default_currency`, `telegram_username`, `is_active`, `last_login_ip`, `login_count`, `preferences`.
- Missing columns in real DB state previously caused startup/auth issues.
- Fixes are covered via `003` and `004`, making login and `ensure_superuser` resilient to schema drift.

---

## 8) Operational Risks and Controls

### Main risks
- Legacy and v2 tables coexisting after failed/partial migration operations.
- Enum/type leftovers (`userplan`, related old types) conflicting with v2 expectations.
- Extension/operator mismatch (`pg_trgm`, `gin_trgm_ops`) causing index/runtime failures.
- Background jobs writing data while schema is in transition.

### Controls in place
- Migration guards in Alembic env for v2 detection/reset behavior.
- SQL statement splitter for asyncpg-safe single-statement execution.
- Additive fix migrations (`003`, `004`) that avoid brittle one-shot assumptions.
- Disabled beat schedule during stabilization.

---

## 9) Current Source-of-Truth Files

- Project overview:
  - `Imperecta_Cursor_Project_Description.md`
- Backend audit:
  - `backend_full_audit_report.md`
- Parser/scraper audit:
  - `parsers_audit.md`
- Migrations:
  - `backend/alembic/env.py`
  - `backend/alembic/versions/001_v2_schema.py`
  - `backend/alembic/versions/002_v2_additions.py`
  - `backend/alembic/versions/003_fix_users_columns.py`
  - `backend/alembic/versions/004_fix_real_state.py`

---

## 10) Practical Verification Checklist

For deployment validation:
- `alembic upgrade head` reaches `004_fix_real_state` without errors.
- App startup succeeds (`from app.main import app`).
- `users` table contains v2-required columns.
- Legacy tables/types are absent or neutralized.
- `pg_trgm` extension is available.
- Beat schedule remains empty until explicitly re-enabled.

