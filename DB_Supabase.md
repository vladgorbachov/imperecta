# DB_Supabase

## Snapshot

- Snapshot date (UTC): 2026-05-28
- Source of truth:
  - ORM models in `backend/app/models/`
  - Alembic migrations in `backend/alembic/versions/`
  - REST metadata at Supabase `/rest/v1/`

## Current migration state

- Migration chain in repository:
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
- `010` adds universal discovery fields on `dim_marketplace`.
- `011` adds listing lifecycle fields (`fact_listing.is_active`, `fact_listing.last_price_changed_at`) and `no_change` status into `scrape_logs` CHECK.

## Schema overview

Project uses star schema + operational tables:

- Dimensions: `dim_*`
- Facts: `fact_*`
- Application tables: users, subscriptions, alerts, digests, AI chat, scrape jobs/logs, exports

Key high-load tables:

- `fact_listing` (URL-level identity + denormalized current state)
- `fact_price` (history by `date_id`, partitioned)
- `scrape_logs` (attempt-level diagnostics)

## Runtime data integrity rules

- `fact_price` is written only when:
  - name is present (`product_name` or `title`)
  - `price > 0`
  - currency is non-empty
- No silent fallback currency (`USD` fallback is not used).
- Listing dedup uses `fact_listing.url_hash`.
- Worker-safe date creation in `dim_date` uses select + upsert pattern.

## Important operational tables

- `scrape_jobs`: pipeline job envelope and metadata
- `scrape_logs`: per-attempt execution record
- `alerts` / `alert_events`: user alerting
- `ai_chat_sessions` / `ai_chat_messages`: AI chat history
- `api_logs` / `data_exports`: API observability and exports

## Supabase / Alembic specifics

- Alembic version table is in schema `alembic_meta`.
- `backend/alembic/env.py` commits explicitly after `run_sync` to prevent async rollback on context exit.
- Supabase URL normalization (`postgresql://` -> `postgresql+asyncpg://`) is handled in `backend/app/config.py`.

## Live REST snapshot (2026-05-28)

Observed entities include:

- `dim_marketplace`, `dim_product`, `fact_listing`, `fact_price`, `scrape_jobs`, `scrape_logs`
- user-facing/app tables: `users`, `user_products`, `alerts`, `digests`, `ai_chat_*`, `api_logs`, `data_exports`
- market data facts: `fact_currency_rate`, `fact_crypto_price`, `fact_commodity_price`, `fact_fuel_price`
- MVs: `mv_daily_price_summary`, `mv_marketplace_health`

Row counts fluctuate and should be checked live; structure and constraints are defined by models + migrations above.

## Quick verification SQL

```sql
SELECT COUNT(*) FROM fact_listing;
SELECT COUNT(*) FROM fact_price;
SELECT COUNT(*) FROM scrape_logs;
SELECT COUNT(*) FROM dim_product;
```

```sql
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position;
```
