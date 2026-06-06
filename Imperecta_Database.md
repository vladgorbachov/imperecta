# Imperecta — База данных (Supabase PostgreSQL)

**Актуально на:** 2026-06-03 (head `015`; app `6701bba` + scoped scrape по `marketplace_code`)  
**Источники:** `backend/app/models/`, `backend/alembic/versions/`, runtime rules в `scraper/service.py`.

---

## 1. Обзор

| Аспект | Значение |
|--------|----------|
| СУБД | PostgreSQL (Supabase) |
| Паттерн | Star schema + operational tables |
| Backend access | Direct URL, table owner — **RLS bypass** |
| Supabase REST | RLS enabled (migration 012) |
| Alembic version | Schema `alembic_meta.alembic_version` |
| Head revision | `015_fact_price_default_partition` |

При старте API: `alembic upgrade head` (subprocess).

---

## 2. Цепочка миграций

| # | Revision | Суть |
|---|----------|------|
| 001 | `v2_schema` | Base v2 + seeds |
| 002 | `v2_additions` | Additions |
| 003 | `fix_users_columns` | users columns |
| 004 | `fix_real_state` | Production repair |
| 005 | `scrape_logs_technical_error` | Status `technical_error` |
| 006 | `scrape_logs_status_length` | VARCHAR(50) |
| 007 | `fix_migration_deadlock_and_meta` | `alembic_meta` schema |
| 008 | `fix_alembic_version_length` | Wider `version_num` |
| 009 | `full_v2_schema_rebuild` | Idempotent full v2 DDL |
| 010 | `discovery_universal_columns` | Universal discovery on marketplace |
| 011 | `dedup_and_listing_lifecycle` | `is_active`, `last_price_changed_at`, `no_change` |
| 012 | `enable_rls_public_tables` | RLS policies |
| 013 | `search_trend_source_generic` | Generic `fact_search_trend.source` CHECK |
| 014 | `marketplace_scrape_tier` | `dim_marketplace.scrape_tier` 1–3 |
| 015 | `fact_price_default_partition` | `fact_price_202606`–`202612` + `fact_price_default` (**head**) |

**Правила:** не редактировать старые revisions; один statement per `op.execute()` для asyncpg; `IF NOT EXISTS` для repair.

---

## 3. Таблицы

### 3.1 Core (`models/core.py`)

| Table | ORM | Назначение |
|-------|-----|------------|
| `users` | User | Auth, plan, superuser, language |
| `user_subscriptions` | UserSubscription | Billing period |
| `user_products` | UserProduct | User catalog links |

**Plan CHECK:** `trial`, `starter`, `business`, `pro`, `enterprise` (см. entitlements).

### 3.2 Dimensions (`models/dimensions.py`)

| Table | ORM |
|-------|-----|
| `dim_date` | DimDate |
| `dim_currency` | DimCurrency |
| `dim_country` | DimCountry |
| `dim_marketplace` | DimMarketplace |
| `dim_category` | DimCategory |
| `dim_brand` | DimBrand |
| `dim_product` | DimProduct |
| `dim_seller` | DimSeller |

**`dim_marketplace` (parsing + scrape):** **`marketplace_code`** (unique, used in scoped pipeline filter), `code`, `base_url`, `is_active`, `requires_js`, **`scrape_tier`** (INTEGER 1–3, default 1, indexed), `scraper_config` JSONB, custom selectors (010), `product_quota`, `products_in_pool`, `last_discovery_*`, `discovery_error_count`, `discovered_category_urls` (JSONB), `last_category_recon_at`, `sitemap_url`, `last_sitemap_harvest_at`.

**Scoped pipeline:** `POST run-pipeline { marketplace_codes }` → orchestrator фильтрует listings через `dim_marketplace.marketplace_code IN (...)`.

**`scrape_tier` semantics:**

| Value | Intended use | App support |
|-------|--------------|-------------|
| 1 | SSR shops: Decodo + httpx + Playwright | Implemented |
| 2 | SPA + network intercept + stealth | DB only → `NotImplementedError` |
| 3 | Hostile + residential + LLM fallback | DB only → `NotImplementedError` |

Existing rows get `DEFAULT 1` — behavior unchanged until tier is raised and layers implemented.

**Seeds в миграциях:** dates 2024–2030, ~30 currencies, ~44 countries — `ON CONFLICT DO NOTHING`.

### 3.3 Facts (`models/facts.py`)

| Table | ORM | Notes |
|-------|-----|-------|
| `fact_listing` | FactListing | URL identity, denormalized `last_*` |
| `fact_price` | FactPrice | **Partitioned** by `date_id` |
| `fact_review` | FactReview | |
| `fact_stock` | FactStock | |
| `fact_search_trend` | FactSearchTrend | `source`: google_trends, amazon_trends, custom (013) |
| `fact_currency_rate` | FactCurrencyRate | Market data |
| `fact_tariff` | FactTariff | |
| `fact_promo` | FactPromo | |
| `fact_crypto_price` | FactCryptoPrice | |
| `fact_commodity_price` | FactCommodityPrice | |
| `fact_fuel_price` | FactFuelPrice | |

#### `fact_listing`

| Column | Role |
|--------|------|
| `external_url` | Canonical URL |
| `url_hash` | SHA256, **UNIQUE** dedup |
| `last_price`, `last_currency_code`, `last_in_stock` | Current snapshot |
| `consecutive_errors`, `last_error` | Scrape health |
| `is_active` | Lifecycle; false after 15 errors (app logic) |
| `last_price_changed_at` | Last real price change |
| `scrape_interval_minutes` | Reschedule hint |

Indexes: `idx_listing_url_hash` UNIQUE, `idx_listing_active` partial, marketplace/product FK indexes.

#### `fact_price`

- PK includes `listing_id`, `date_id` (YYYYMMDD int).
- **Parent table** `fact_price` — RANGE partition by `date_id` (from migration `009`).
- **Monthly children:** `fact_price_YYYYMM` — bounds `FROM (YYYYMM01) TO (next month 01)`.
- **DEFAULT child:** `fact_price_default` — catch-all если месячной партиции нет (migration `015`); строки следует периодически переносить в явные месячные партиции.
- **015 (2026-06-03):** добавлены `fact_price_202606` … `fact_price_202612` (idempotent `IF NOT EXISTS`).
- **Rolling maintenance:** Celery `ensure_fact_price_partitions` — создаёт партиции на +1…+3 месяца вперёд.
- **One snapshot per listing per day:** app deletes existing row for `(listing_id, date_id)` before insert.
- `price_change_pct` capped at ±9_999.9999% in app logic.

**Операционная ошибка без партиции:** `no partition of relation "fact_price" found for row` — лечится `alembic upgrade head` и/или `ensure_fact_price_partitions`.

### 3.4 App tables (`models/app_tables.py`)

| Table | ORM |
|-------|-----|
| `alerts` | Alert |
| `alert_events` | AlertEvent |
| `digests` | Digest |
| `ai_chat_sessions` | AIChatSession |
| `ai_chat_messages` | AIChatMessage |
| `scrape_jobs` | ScrapeJob |
| `scrape_logs` | ScrapeLog |
| `api_logs` | ApiLog |
| `data_exports` | DataExport |

#### `scrape_jobs`

- `job_type`: e.g. `full_pipeline_test`
- `status`: queued, running, completed, failed, cancelled
- `config` JSONB: metadata (stage, timings, per_marketplace, celery_task_id)

#### `scrape_logs`

| Column | Notes |
|--------|-------|
| `status` | VARCHAR(50) + CHECK |
| `technical_error` | TEXT (005) |
| `duration_ms`, `scraper_layer` | Diagnostics |
| `listing_id`, `scrape_job_id` | FK |

**Statuses:** `success`, `no_change`, `error`, `timeout`, `blocked`, `captcha`, `not_found`, `price_not_found`, `parse_error`, `missing_critical_data`, `technical_error`.

**Runtime repair:** если БД на старом CHECK/VARCHAR(20) — `GlobalScrapeService` может выполнить `ALTER` при первой ошибке вставки.

---

## 4. Materialized views

| View | Purpose |
|------|---------|
| `mv_daily_price_summary` | Daily aggregates |
| `mv_marketplace_health` | Marketplace health for admin |

Refresh: Celery `refresh_materialized_views` (concurrent where supported).

---

## 5. Integrity rules (application layer)

### 5.1 `fact_price` write gate

Все условия одновременно:

1. `product_name` OR non-empty `title`
2. `price > 0`
3. `currency` non-empty
4. `len(currency_raw) < 50`
5. `currency.upper()` ∈ marketplace whitelist (country currency + EUR + USD + `scraper_config.allowed_currencies`)

Иначе: skip insert; `scrape_logs` → `parse_error` или `missing_critical_data`.

### 5.2 `no_change`

Если price/currency/stock совпадают с `listing.last_*` (tolerance 0.001 on price):

- No new `fact_price` row
- Update `last_checked_at`
- `scrape_logs.status = no_change`

### 5.3 Listing deactivation

`consecutive_errors >= 15` on failed scrape → `is_active = false` (excluded from pool batch).

### 5.4 No fake defaults

- No USD fallback
- No `price = 0` substitute
- `last_in_stock` chain ends at `False`, not NULL

### 5.5 `dim_date`

Deadlock-safe: SELECT → INSERT ON CONFLICT DO NOTHING → SELECT.

### 5.6 URL dedup

`FactListing.compute_url_hash(normalized_url)` — unique index.

---

## 6. RLS (012)

**Цель:** restrict PostgREST if keys leak.

- `ENABLE ROW LEVEL SECURITY` on public business tables.
- Backend service role bypasses as owner.
- Policies defined in `012_enable_rls_public_tables.py`.

---

## 7. Retention

`cleanup_old_data` (Celery): aged `scrape_logs`, `api_logs`, chat messages, `alert_events` — см. `workers/cleanup_tasks.py`.

---

## 8. Stale pipeline jobs (DB effect)

`ParsingAdminService._fail_stale_running_pipeline_jobs`:

- Updates `scrape_jobs.status` → failed
- Sets metadata `error = stale_pipeline_timeout: …`
- Invoked on admin reads (active job, status, runs)

---

## 9. Verification SQL

```sql
SELECT version_num FROM alembic_meta.alembic_version;

SELECT COUNT(*) FROM fact_listing WHERE is_active = true;
SELECT COUNT(*) FROM fact_price;
SELECT status, COUNT(*) FROM scrape_logs GROUP BY 1 ORDER BY 2 DESC;

SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public' AND rowsecurity
ORDER BY 1;
```

```sql
SELECT inhrelid::regclass AS partition
FROM pg_inherits
JOIN pg_class parent ON inhparent = parent.oid
WHERE parent.relname = 'fact_price';
```

---

## 10. Connection strings

| Consumer | Driver |
|----------|--------|
| FastAPI | `postgresql+asyncpg://` |
| Celery / sync scrape | psycopg2 via `sync_session_factory` |

Normalizer in `Settings.validate_database_url`.

---

## 11. ORM metadata note

**Migration 013:** перенос legacy `kaspi_trends`, `allegro_trends` → `custom`; CHECK только `google_trends`, `amazon_trends`, `custom`.

**Migration 014:** `scrape_tier` on `dim_marketplace`.  
**Migration 015:** monthly partitions Jun–Dec 2026 + `fact_price_default`.

`models/__init__.py` docstring may reference older head — **trust migration files** (`015_*`) over comments.

---

## 12. Источники

| Area | Path |
|------|------|
| Models | `backend/app/models/*.py` |
| Migrations | `backend/alembic/versions/` |
| Persist rules | `backend/app/modules/scraper/service.py` |
| Partitions | `backend/app/workers/maintenance_tasks.py`, `015_fact_price_default_partition.py` |
| Admin stale | `backend/app/modules/admin/parsing_admin.py` |

Связанные документы: `Imperecta_Architecture.md`, `Imperecta_Parsing.md`, `.cursor/rules/database.mdc`.
