# Imperecta Context (Current State)

## 0) Snapshot (2026-05-27)

- **Data Collection observability (current admin focus):**
  - Backend: `/api/admin/parsing/users-detailed`, `/api/admin/parsing/marketplaces-detailed`, `/api/admin/parsing/job-live-feed/{job_id}`, `/api/admin/parsing/active-job`.
  - Frontend: `AdminPage` tabs reorganized to **Data Collection**, **Market Overview**, **Users Management** with live charts/logs and ETA forecast.
  - Data Collection widgets are driven by live API data (`job-live-feed` + `job-status` + `test-runs`), not mock values.

- **Pipeline stability hardening (latest):**
  - `ParsingAdminService` now enforces single active `full_pipeline_test` run.
  - Stale `running` full-pipeline jobs are auto-failed after inactivity timeout.
  - Pipeline metadata tracks `last_activity_at`; live stage resolution now reflects real scrape activity.
  - `run_full_pipeline_test` updates stage heartbeat during discovery/scrape/persist.
  - Finalization now merges `scrape_logs` stats even if discovery seed metadata is incomplete.

- **Discovery and extraction hardening (latest):**
  - Discovery now tries fallback seed URLs (`/catalog`, `/products`, `/shop`, locale variants) when base seed fails.
  - Price parser now rejects unrealistic huge numeric tokens (catalog IDs/barcodes) to reduce `price_overflow`.
  - Failed scrape logs now always include non-empty `error_message` fallback.

- **Git head:** `b0a0a55` — *Stabilize pipeline and discovery flow*.
- Description docs aligned: `Imperecta_Full_Development_Context.md`, `parsers_audit.md`, `imperecta_context.md` (Alembic head **009**, `scrape_logs.status` **VARCHAR(50)**).
- **Deploy target:** Railway (backend + celery-worker + celery-beat), Cloudflare Pages (frontend), Supabase (PostgreSQL), Upstash (Redis). Локальная разработка — только `docker compose up` + корневой `.env` (gitignored).
- **Config (`backend/app/config.py`):** `DATABASE_URL` и `REDIS_URL` обязательны; `app_env=production`, `allowed_origins=https://imperecta.pages.dev`; Supabase URL `postgresql://` автоматически нормализуется в `postgresql+asyncpg://`.
- **Legacy cleanup (v2-only):** удалены runtime `app/api/*`, `app/services/*`, legacy Celery tasks (`scrape_single`, `scrape_user_products`, `scrape_all`), admin endpoints `trigger-scrape`, `scrape-activity`, `error-distribution`, `clear-test-data`, `marketplaces/deduplicate`, `DELETE /api/pool/products/bulk`.
- **Admin clear-pool:** `POST /api/admin/products/clear-pool` — транзакционный hard reset pool-данных: TRUNCATE `fact_price`, `fact_review`, `fact_stock`, `fact_promo`, `fact_listing`, `scrape_logs`, `scrape_jobs`, `dim_product`, `dim_marketplace`; DELETE `user_products`; nullify alert FKs; сохраняются `dim_date`, `dim_currency`, `dim_country`, `users`, subscriptions, alerts, digests и прочие системные таблицы. Ответ: `{"status":"pool_cleared","deleted_marketplaces":N,"deleted_listings":N,"deleted_prices":N,"time_ms":N}`.
- **DB dumps in repo:** `db/backups/imperecta_20260414_2040.sql.gz` (latest, for Windows/dev restore via `pg_restore`); новые дампы gitignored except `.gitkeep`.
- **Alembic head:** `009_full_v2_schema_rebuild` — идемпотентная полная DDL v2 (расширения, **`alembic_meta`**, **31** таблица в `public`, партиции **`fact_price`**, MV, сиды `dim_*`). Предшествуют **`008_fix_alembic_version_length`** (ширина **`version_num`**), **`007`** (repair **`alembic_meta`**, таймауты, опциональный reset пустого **`public`**), **`005`**/**`006`** — **`scrape_logs`**. **`alembic/env.py`:** после `run_sync(do_run_migrations)` — **`await connection.commit()`** (иначе DDL мог откатываться при выходе из async-контекста). Drift stamp в **`env.py`**: **`009_full_v2_schema_rebuild`**. ORM **`ScrapeLog.status`** = **`String(50)`**; см. **`errors.SCRAPE_LOG_STATUSES`**.
- **`app/main.py` lifespan:** `alembic upgrade head` (subprocess) → **`ensure_superuser`** → **`Base.metadata.create_all`** (ошибки логируются, процесс не падает); webhook Telegram — в фоне.
- Parser runtime: no `engine.py` under `modules/scraper`; path remains `tasks → discovery/service → scraper_pool → extractors`.
- **Marketplaces:** `MarketplaceService` + `modules/marketplaces/api.py` persist rows in `dim_marketplace` (add-by-url, import, delete, quotas, `requires_js`, logs). Endpoint **`POST /api/admin/marketplaces/deduplicate`** removed. Pool/diagnostics/cleanup: `core/api_admin` + `scraper/api`.
- Celery Beat: `scheduler.py` sets `celery_app.conf.beat_schedule = {}` (no periodic enqueue).
- **Pool scraping in workers:** `GlobalScrapeService` uses **sync `Session`** (`sync_session_factory` from `database.py`). Only `ScraperPool.scrape_product` runs async inside `_run_coro_in_worker(...)` to avoid `MissingGreenlet` in prefork workers. Discovery tasks still use a dedicated async engine + `_run_async`.
- **`GlobalScrapeService.scrape_product` (persistence layer, `modules/scraper/service.py`):**
  - On **`result.success`:** clears **legacy** `listing.last_error` and `listing.consecutive_errors` immediately (before branching on `data`). Failed pool responses (`not result.success`) still increment `consecutive_errors` and set `last_error`; a successful response with **no** extracted `data` no longer increments the error counter (only hard failures do).
  - **`fact_price` write gate:** `product_name_ok` is true if **`product_name` or `title`** is present (extractors often populate `title` only). Row is written only when `product_name_ok`, `price > 0`, and non-empty **currency** (no default USD).
  - **`dim_product`:** if `product_name` is empty but **`title`** is present, **`dim_product.name`** (and `name_normalized`) are updated from **title** (placeholder replacement path still applies when `product_name` is non-empty).
  - **`last_in_stock`:** `getattr(result, "in_stock", None) or getattr(data, "in_stock", None) or False` so listings and `fact_price.in_stock` are never left as ambiguous `NULL` when availability is unknown (UI can show a boolean).
  - **`dim_date` for today:** `_today_date_id` is **deadlock-safe**: `SELECT` by `date_id` → if missing, **`INSERT … ON CONFLICT (date_id) DO NOTHING`** (PostgreSQL) → `flush()` → **`SELECT` again**; concurrent workers do not rely on `add`+`flush` alone.
  - **Logging (troubleshooting):** `EXTRACTED →` (raw extractor fields), `FINAL PERSIST` (product_name, title, price, currency, in_stock, `log_status`), after successful DB commit **`SCRAPE COMPLETE listing_id=… status=… price=…`**, then `pool_scrape done`.
- **`scrape_logs`:** extended status values include `missing_critical_data`, `price_not_found`, **`technical_error`** (model CHECK + **`VARCHAR(50)`**; Celery `tasks.py` — **`_persist_technical_error_log`** при необработанных исключениях в pool-задачах). `_determine_log_status` takes optional `data=` from `scrape_product`; unit tests may pass explicit `has_title`/`has_price` without `data=`. When `data` is passed, logic distinguishes dataclasses **with** a `product_name` field (strict catalog-quality rules) vs legacy **title-only** payloads (`ExtractedProduct`).
- **Tests (scraper):** каталоги **`backend/tests/test_scraper_unit/`** и **`backend/tests/test_scraper_integration/`** (в т.ч. **`test_migrations_upgrade.py`**: `alembic upgrade head`, длина колонки `status`, двойной прогон head) плюс **`backend/tests/fixtures/scraper_fixtures.py`**. Отдельные файлы `test_scraper_persistence.py` / `test_scraper_extractors.py` в корне `tests/` **удалены** — сценарии перенесены в `test_scraper_unit/` (в т.ч. persistence, extractors, tasks, `technical_error`).
- **Git policy:** do **not** add commit trailers such as `Made-with: Cursor`.

## 0.1) Parser Runtime Update (2026-03-24)

- `backend/app/modules/scraper/engine.py` removed from production runtime.
- Canonical parser path: `tasks -> discovery/service -> scraper_pool -> extractors`.
- `scraper_pool.py` is the single fetch+extract facade for scraping operations.
- `PoolScrapeResult` contract is expanded with quality metadata:
  - `is_partial`, `is_empty`, `fields_extracted`, `fields_missing`.
- `DiscoveryCrawler.discover()` now returns structured `DiscoveryResult` dataclass instead of a dict.
- Persistence path in `service.py` updated:
  - no fallback currency default (`USD` removed),
  - `FactPrice` is skipped when currency is missing or title/price invalid,
  - stock/availability: optional (`ExtractedProduct` has no `in_stock` field; safe getattr / `None`),
  - `scrape_logs` records each attempt (success/failure/technical metadata); see 2026-04-01 snapshot for sync session + status mapping.
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
- Startup responsibilities: `alembic upgrade head`, `ensure_superuser`, `create_all`, Telegram webhook (see `main.py` lifespan).

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

Current chain (head **`009_full_v2_schema_rebuild`**):
1. `001_v2_schema`
2. `002_v2_additions`
3. `003_fix_users_columns`
4. `004_fix_real_state`
5. `005_scrape_logs_technical_error`
6. `006_scrape_logs_status_length`
7. `007_fix_migration_deadlock_and_meta`
8. `008_fix_alembic_version_length`
9. **`009_full_v2_schema_rebuild`** (head)

### Why 005–009 exist
- **005:** Ensures DB CHECK `ck_scrape_logs_status` allows **`technical_error`** (idempotent if `scrape_logs` missing), aligned with ORM and worker error logging.
- **006:** Widens **`scrape_logs.status`** to **`VARCHAR(50)`** for production drift (e.g. legacy `VARCHAR(20)`).
- **007:** Repairs **`alembic_meta.alembic_version`** when empty but v2 exists; sets session DDL timeouts; optional recreate of empty **`public`** only when safe (see migration file). **`env.py`** mirrors meta repair + `render_item` + `lock_timeout`/`statement_timeout` in `connect_args`.
- **008:** Widens **`alembic_meta.alembic_version.version_num`** to **VARCHAR(255)** for long revision ids.
- **009:** Idempotent **full v2 star-schema DDL** (no `DROP SCHEMA CASCADE`): creates missing tables, indexes, CHECKs, **`fact_price`** monthly partitions, materialized views, and **`dim_*`** seeds with **`ON CONFLICT DO NOTHING`**. Use when earlier revisions were stamped without real DDL (Docker/Supabase-safe).

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
- Migration guards in Alembic env for v2 detection/reset behavior, **`alembic_meta`** table creation, and drift stamp **`009_full_v2_schema_rebuild`** when v2 exists but version rows are missing.
- SQL statement splitter for asyncpg-safe single-statement execution (migrations **001**, **005–007**).
- Additive fix migrations (`003`, `004`) that avoid brittle one-shot assumptions.
- Disabled beat schedule during stabilization.

---

## 9) Current Source-of-Truth Files

- Full development context (AI agent):
  - `Imperecta_Full_Development_Context.md`
- Parser/scraper audit:
  - `parsers_audit.md`
- Runtime snapshot:
  - `imperecta_context.md`
- Local DB restore (Windows / new machine):
  - `db/backups/imperecta_20260414_2040.sql.gz` — latest committed dump
  - `docker-compose.yml` — postgres + redis + backend + celery + frontend
- Migrations:
  - `backend/alembic/env.py`
  - `backend/alembic/versions/001_v2_schema.py` … `009_full_v2_schema_rebuild.py` (see chain in §5)

---

## 10) Practical Verification Checklist

For deployment validation:
- `alembic upgrade head` reaches **`009_full_v2_schema_rebuild`** without errors; **`public`** has **31** base tables (+ **`fact_price`** partitions); **`alembic_meta.alembic_version`** has one row.
- App startup succeeds (`from app.main import app`).
- `users` table contains v2-required columns.
- Legacy tables/types are absent or neutralized.
- `pg_trgm` extension is available.
- Beat schedule remains empty until explicitly re-enabled.

