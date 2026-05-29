# Imperecta — База данных (Supabase PostgreSQL)

**Актуально на:** 2026-05-28  
**Источники истины:** `backend/app/models/`, `backend/alembic/versions/`, live schema в Supabase.

---

## 1. Обзор

- **СУБД:** PostgreSQL 15+ (Supabase managed).
- **Паттерн:** star schema для аналитики + операционные таблицы приложения.
- **Доступ backend:** прямое подключение по `DATABASE_URL` (asyncpg / psycopg2) — **table owner**, RLS не применяется к backend-роли.
- **Supabase REST:** PostgREST `/rest/v1/` — RLS включён (migration `012`) как defense in depth при утечке anon/service keys.
- **Версионирование схемы:** Alembic; таблица версий в схеме **`alembic_meta.alembic_version`** (переживает `DROP SCHEMA public` в repair-миграциях).

---

## 2. Цепочка миграций

| Rev | ID | Суть |
|-----|-----|------|
| 001 | `v2_schema` | Базовая v2 star schema + seeds |
| 002 | `v2_additions` | Дополнительные объекты |
| 003 | `fix_users_columns` | Колонки users |
| 004 | `fix_real_state` | Repair production drift |
| 005 | `scrape_logs_technical_error` | Статус `technical_error` |
| 006 | `scrape_logs_status_length` | VARCHAR(50) для status |
| 007 | `fix_migration_deadlock_and_meta` | alembic_meta schema |
| 008 | `fix_alembic_version_length` | Widen `version_num` |
| 009 | `full_v2_schema_rebuild` | Идемпотный полный rebuild v2 |
| 010 | `discovery_universal_columns` | Universal discovery на `dim_marketplace` |
| 011 | `dedup_and_listing_lifecycle` | `is_active`, `last_price_changed_at`, `no_change` |
| 012 | `enable_rls_public_tables` | RLS на public tables (**head**) |

**Head:** `012_enable_rls_public_tables`

### Правила миграций

- Не изменять уже применённые файлы — только новые revisions.
- **asyncpg:** один SQL statement на `op.execute()`; батчи через `_split_sql_statements()`.
- Использовать `IF NOT EXISTS` / `IF EXISTS` для repair.
- Supabase: избегать `DROP SCHEMA public CASCADE` — только точечные `DROP TABLE`.

### Alembic runtime

`backend/alembic/env.py` — явный **commit** после `connection.run_sync()` чтобы async context manager не откатывал DDL.

При старте приложения: `main.py` → `alembic upgrade head` (subprocess).

---

## 3. Схемы и namespaces

| Schema | Содержание |
|--------|------------|
| `public` | Все business tables, MVs, indexes |
| `alembic_meta` | `alembic_version` |

---

## 4. Таблицы по группам

### 4.1 Core (`models/core.py`)

| ORM | Table | Назначение |
|-----|-------|------------|
| `User` | `users` | Аккаунты, JWT, superuser flag, language |
| `UserSubscription` | `user_subscriptions` | План, лимиты, период |
| `UserProduct` | `user_products` | Товары пользователя, ссылки на dim_product |

### 4.2 Dimensions (`models/dimensions.py`)

| ORM | Table |
|-----|-------|
| `DimDate` | `dim_date` |
| `DimCurrency` | `dim_currency` |
| `DimCountry` | `dim_country` |
| `DimMarketplace` | `dim_marketplace` |
| `DimCategory` | `dim_category` |
| `DimBrand` | `dim_brand` |
| `DimProduct` | `dim_product` |
| `DimSeller` | `dim_seller` |

**`dim_marketplace` (ключевые поля для parsing):**

- `code`, `name`, `base_url`, `is_active`
- `requires_js`, `scraper_config` (JSONB)
- Discovery: universal columns (migration `010`) — selectors, sitemap, category patterns
- `last_discovery_at`, `products_in_pool`, discovery stats

**Seeds (в миграциях):**

- `dim_date`: 2024-01-01 … 2030-12-31
- `dim_currency`: ~30 валют
- `dim_country`: ~44 страны (Europe + CIS)

### 4.3 Facts (`models/facts.py`)

| ORM | Table | Примечание |
|-----|-------|------------|
| `FactListing` | `fact_listing` | URL-level identity, denormalized last_* |
| `FactPrice` | `fact_price` | **Partitioned** by `date_id` |
| `FactReview` | `fact_review` | |
| `FactStock` | `fact_stock` | |
| `FactSearchTrend` | `fact_search_trend` | |
| `FactCurrencyRate` | `fact_currency_rate` | Market data |
| `FactTariff` | `fact_tariff` | |
| `FactPromo` | `fact_promo` | |
| `FactCryptoPrice` | `fact_crypto_price` | |
| `FactCommodityPrice` | `fact_commodity_price` | |
| `FactFuelPrice` | `fact_fuel_price` | |

#### `fact_listing` — центральная сущность пула

| Поле | Роль |
|------|------|
| `external_url` | Канонический URL |
| `url_hash` | SHA256, **unique**, dedup при discovery |
| `product_id`, `marketplace_id`, `seller_id` | FK |
| `last_price`, `last_currency_code`, `last_in_stock`, … | Denormalized текущее состояние |
| `consecutive_errors`, `last_error` | Health scrape |
| `is_active` | Lifecycle (011) |
| `last_price_changed_at` | Когда цена реально изменилась (011) |
| `scrape_interval_minutes` | Интервал повторного scrape |
| `scraper_config` | JSONB overrides |

**Constraints:**

- `uq_fact_listing_product_marketplace_seller_url`
- `idx_listing_url_hash` UNIQUE
- `idx_listing_active` partial WHERE `is_active = true`

#### `fact_price` — история

- FK: `listing_id`, `date_id` → `dim_date`
- Поля: `price`, `original_price`, `currency_code`, `product_name`, `title`, `in_stock`, …
- **Partition key:** `date_id` (integer YYYYMMDD)
- Партиции: `fact_price_YYYYMM` — создаются задачей `ensure_fact_price_partitions` на 3 месяца вперёд

### 4.4 App tables (`models/app_tables.py`)

| ORM | Table |
|-----|-------|
| `Alert` | `alerts` |
| `AlertEvent` | `alert_events` |
| `Digest` | `digests` |
| `AIChatSession` | `ai_chat_sessions` |
| `AIChatMessage` | `ai_chat_messages` |
| `ScrapeJob` | `scrape_jobs` |
| `ScrapeLog` | `scrape_logs` |
| `ApiLog` | `api_logs` |
| `DataExport` | `data_exports` |

#### `scrape_jobs`

- Parent jobs для pipeline (`job_type = full_pipeline_test`)
- `status`, `started_at`, `completed_at`
- `config` JSONB: metadata store (stage, counters, celery_task_id, marketplace filter)

#### `scrape_logs`

- Одна запись ≈ одна попытка scrape listing
- `status` VARCHAR(50) + CHECK constraint
- `technical_error` TEXT (migration 005)
- `duration_ms`, `scraper_layer`, extracted fields snapshot

**Допустимые статусы (canonical):**

`success`, `error`, `timeout`, `blocked`, `captcha`, `not_found`, `price_not_found`, `parse_error`, `missing_critical_data`, `technical_error`, **`no_change`** (011).

---

## 5. Materialized views

| View | Назначение |
|------|------------|
| `mv_daily_price_summary` | Агрегаты цен по дням |
| `mv_marketplace_health` | Health маркетплейсов для admin |

Обновление: Celery `refresh_materialized_views` (concurrent refresh где поддерживается).

---

## 6. Правила целостности данных (код)

Эти правила **не** только CHECK в БД — enforced в `GlobalScrapeService` / persistence layer.

### 6.1 Запись `fact_price`

Запись **только если:**

1. `product_name` OR `title` — non-empty
2. `price > 0`
3. `currency` — non-empty string

**Запрещено:** silent fallback `USD`, `price = 0`, подстановка fake name.

### 6.2 `no_change`

Если scrape успешен, но цена/ключевые поля не изменились → `scrape_logs.status = no_change`, `fact_price` может не писаться.

### 6.3 Listing dedup

- Discovery: `FactListing.compute_url_hash(url)` → upsert by `url_hash`
- Unique index на `url_hash`

### 6.4 `dim_date` в воркере

Паттерн deadlock-safe:

```text
SELECT date_id → INSERT ON CONFLICT DO NOTHING → flush → SELECT
```

### 6.5 `last_in_stock`

Цепочка: `result.in_stock` → `data.in_stock` → `False` (никогда NULL в persist).

### 6.6 Price overflow

`MAX_VALID_PRICE = 9_999_999_999.99` — выше или ≤0 отбрасывается в scraper layer.

---

## 7. RLS (migration 012)

**Цель:** если anon/authenticated Supabase keys попадут в REST, строки не читаются без policy.

**Таблицы с ENABLE ROW LEVEL SECURITY** (выборка):

`users`, `user_products`, `user_subscriptions`, все `dim_*`, все `fact_*`, `alerts`, `alert_events`, `digests`, `ai_chat_*`, `scrape_jobs`, `scrape_logs`, `api_logs`, `data_exports`, …

**Backend:** подключается ролью с правами owner → RLS bypass.

**Policies:** по умолчанию restrictive; детали в `012_enable_rls_public_tables.py`.

---

## 8. Индексы и производительность

- FK columns indexed (`product_id`, `marketplace_id`, `listing_id`, `date_id`).
- Partial index на active listings.
- `url_hash` unique — быстрый dedup.
- `fact_price` partition pruning по `date_id`.
- Рекомендация Supabase: `pg_stat_statements`, регулярный VACUUM/ANALYZE на `scrape_logs`, `fact_price` partitions.

---

## 9. Retention и cleanup

**Celery `cleanup_old_data`:**

- Старые `scrape_logs` (по retention policy в task)
- `api_logs`, AI chat messages, `alert_events`

Точные интервалы — в `workers/cleanup_tasks.py`.

---

## 10. URL normalization

`FactListing.compute_url_hash`:

- Нормализация URL (lowercase host, strip tracking params — см. implementation в `facts.py`)
- SHA256 hex → 64 char `url_hash`

---

## 11. Связь ORM ↔ Alembic

`backend/app/models/__init__.py` — re-export всех моделей для `Base.metadata`.

**Важно:** docstring в `__init__.py` может отставать от реального head — ориентир: **migration files**, не комментарий.

---

## 12. Проверочные SQL

```sql
-- Head migration
SELECT version_num FROM alembic_meta.alembic_version;

-- Объёмы
SELECT COUNT(*) FROM fact_listing;
SELECT COUNT(*) FROM fact_price;
SELECT COUNT(*) FROM scrape_logs;
SELECT COUNT(*) FROM dim_product;

-- RLS status
SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public' AND rowsecurity = true
ORDER BY tablename;

-- Партиции fact_price
SELECT inhrelid::regclass AS partition
FROM pg_inherits
JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
WHERE parent.relname = 'fact_price';
```

```sql
-- Схема колонок (обзор)
SELECT table_name, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position;
```

---

## 13. Supabase REST snapshot

При обращении к `/rest/v1/` ожидаемые entity (имена таблиц):

- Dimensions: `dim_marketplace`, `dim_product`, …
- Facts: `fact_listing`, `fact_price`, market data facts
- Ops: `users`, `scrape_jobs`, `scrape_logs`, `alerts`, `digests`, `ai_chat_sessions`, …
- MVs: `mv_daily_price_summary`, `mv_marketplace_health`

Row counts динамичны — для аудита использовать COUNT на prod read-replica или Supabase SQL editor.

---

## 14. Конфигурация подключения

`backend/app/config.py`:

```text
postgresql://user:pass@host:5432/db   →  postgresql+asyncpg://...  (API)
postgresql://...                       →  psycopg2 (Celery sync)
```

SSL: параметры Supabase pooler — в connection string Railway env.

---

## 15. Файлы-источники

| Область | Путь |
|---------|------|
| Models | `backend/app/models/core.py`, `dimensions.py`, `facts.py`, `app_tables.py` |
| Migrations | `backend/alembic/versions/*.py` |
| Alembic env | `backend/alembic/env.py` |
| Partition task | `backend/app/workers/maintenance_tasks.py` |
| Persist rules | `backend/app/modules/scraper/service.py` |

Связанные документы: `Imperecta_Architecture.md`, `Imperecta_Parsing.md`, `.cursor/rules/database.mdc`.
