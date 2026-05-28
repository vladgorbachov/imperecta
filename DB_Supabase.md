# DB_Supabase

## Source of truth

- ORM models:
  - `backend/app/models/dimensions.py`
  - `backend/app/models/core.py`
  - `backend/app/models/facts.py`
  - `backend/app/models/app_tables.py`
- Migration chain:
  - `backend/alembic/versions/001_v2_schema.py`
  - `backend/alembic/versions/009_full_v2_schema_rebuild.py`
  - `backend/alembic/versions/010_discovery_universal_columns.py`
  - `backend/alembic/versions/011_dedup_and_listing_lifecycle.py`

## Supabase access status

- REST endpoint: `https://qghiocwxypjzuwktpgvd.supabase.co/rest/v1/`
- Current check result: access restored with `SUPABASE_SERVICE_API_KEY` (`HTTP 200` on `dim_marketplace` query).
- DB structure below is documented from the codebase schema (models + migrations).

## Live snapshot (REST, service key)

Snapshot source:
- `GET /rest/v1/` OpenAPI (Swagger 2.0) metadata
- `GET /rest/v1/<table>?select=*&limit=1` with `Prefer: count=exact`

Snapshot (UTC): 2026-05-28

### Exposed entities in REST schema cache

- `ai_chat_messages`
- `ai_chat_sessions`
- `alert_events`
- `alerts`
- `api_logs`
- `data_exports`
- `digests`
- `dim_brand`
- `dim_category`
- `dim_country`
- `dim_currency`
- `dim_date`
- `dim_marketplace`
- `dim_product`
- `dim_seller`
- `fact_commodity_price`
- `fact_crypto_price`
- `fact_currency_rate`
- `fact_fuel_price`
- `fact_listing`
- `fact_price`
- `fact_promo`
- `fact_review`
- `fact_search_trend`
- `fact_stock`
- `fact_tariff`
- `mv_daily_price_summary` (view; count query returned HTTP error)
- `mv_marketplace_health` (view; count query returned HTTP error)
- `scrape_jobs`
- `scrape_logs`
- `user_products`
- `user_subscriptions`
- `users`

### Row counts (live)

- `users`: 4
- `dim_marketplace`: 10
- `dim_product`: 802
- `fact_listing`: 802
- `fact_price`: 822
- `scrape_jobs`: 125
- `scrape_logs`: 994
- `dim_country`: 44
- `dim_currency`: 30
- `dim_date`: 2557
- `ai_chat_messages`: 0
- `ai_chat_sessions`: 0
- `alert_events`: 0
- `alerts`: 0
- `api_logs`: 0
- `data_exports`: 0
- `digests`: 0
- `dim_brand`: 0
- `dim_category`: 0
- `dim_seller`: 0
- `fact_commodity_price`: 0
- `fact_crypto_price`: 0
- `fact_currency_rate`: 0
- `fact_fuel_price`: 0
- `fact_promo`: 0
- `fact_review`: 0
- `fact_search_trend`: 0
- `fact_stock`: 0
- `fact_tariff`: 0
- `user_products`: 0
- `user_subscriptions`: 0

### Live consistency observations

- `fact_listing` and `dim_product` are aligned in volume (`802 / 802`), which indicates discovery insertion path is currently consistent.
- `fact_price` volume is slightly above `fact_listing` (`822`), expected for repeated snapshots over time.
- User-level business tables (`user_products`, alerts, digests, subscriptions history) are currently empty.
- Analytics market-data fact tables (crypto/commodity/fuel/fx/trend) are currently empty in live project.
- Materialized views are present in OpenAPI but not countable with the same request pattern (likely permission or PostgREST cache behavior for views).

## Schema overview

Database follows a star-schema + operational tables pattern:

- Dimensions (`dim_*`) — reference entities.
- Facts (`fact_*`) — time series and listing snapshots.
- Core (`users`, subscriptions, user-product mappings) — application identity and ownership.
- App operational tables — alerts, digests, AI chat, scrape jobs/logs, API logs, exports.

## Tables and relationships

### Dimension layer

#### `dim_date`
- Calendar dimension (`date_id` surrogate in `YYYYMMDD`).
- Referenced by: `fact_price`, `fact_review`, `fact_stock`, `fact_search_trend`, `fact_currency_rate`, `fact_promo`, `fact_crypto_price`, `fact_commodity_price`, `fact_fuel_price`.

#### `dim_currency`
- Currency reference (ISO code PK).
- Referenced by: `dim_country`, `dim_marketplace`, `fact_currency_rate`, `fact_fuel_price`.

#### `dim_country`
- Country dictionary (region/subregion/VAT metadata).
- Referenced by: `dim_marketplace`, `dim_brand`, `fact_search_trend`, `fact_tariff`, `fact_fuel_price`.

#### `dim_marketplace`
- Marketplace registry + scraping/discovery runtime config.
- Key runtime columns:
  - `product_quota`, `products_in_pool`
  - `requires_js`, `rate_limit_delay`
  - `last_discovery_*`, `discovery_error_count`
  - `discovered_category_urls`, `last_category_recon_at` (migration 010)
  - `sitemap_url`, `last_sitemap_harvest_at` (migration 010)
- Referenced by: `fact_listing`, `dim_seller`, `scrape_jobs`, `scrape_logs`, `fact_promo`, `alerts`.

#### `dim_category`
- Hierarchical category tree (`parent_id` self-reference).
- Referenced by: `dim_product`, `fact_search_trend`, `fact_promo`, `alerts`.

#### `dim_brand`
- Brand dimension.
- Referenced by: `dim_product`.

#### `dim_product`
- Canonical product identity (name, normalized name, attributes JSONB).
- Referenced by: `fact_listing`, `user_products`, `fact_search_trend`, `alerts`.

#### `dim_seller`
- Seller/store entity scoped by marketplace.
- Referenced by: `fact_listing`.

### Core application layer

#### `users`
- User identity/auth/preferences.
- Key governance fields:
  - `plan`, `trial_ends_at`
  - `is_superuser`, `is_active`, `force_password_change`
  - `preferences` JSONB
- Referenced by: `user_subscriptions`, `user_products`, `alerts`, `digests`, `ai_chat_sessions`, `scrape_jobs.triggered_by`, `api_logs`, `data_exports`.

#### `user_subscriptions`
- Historical plan state per user.
- FK: `user_id -> users.id`.

#### `user_products`
- User-to-product tracking link.
- FK: `user_id -> users.id`, `product_id -> dim_product.id`.
- Unique pair constraint for user/product ownership.

### Fact layer

#### `fact_listing`
- Product listing identity on specific marketplace URL.
- FK:
  - `product_id -> dim_product.id`
  - `marketplace_id -> dim_marketplace.id`
  - `seller_id -> dim_seller.id`
- Operational state:
  - `last_price`, `last_currency_code`, `last_in_stock`, `last_checked_at`
  - `consecutive_errors`, `last_error`
  - `is_active` (indexed partial active index)
  - `last_price_changed_at` (migration 011)
- URL dedup:
  - `url_hash` unique index.

#### `fact_price`
- Price snapshots partitioned by `date_id` (range partition).
- FK:
  - `listing_id -> fact_listing.id`
  - `date_id -> dim_date.date_id`
  - `scrape_job_id -> scrape_jobs.id`

#### `fact_review`
- Review aggregates per listing/day.
- FK: `listing_id -> fact_listing.id`, `date_id -> dim_date.date_id`.

#### `fact_stock`
- Stock snapshots per listing/day.
- FK: `listing_id -> fact_listing.id`, `date_id -> dim_date.date_id`.

#### `fact_search_trend`
- Search trend metrics by keyword/country/day/source.
- FK: `date_id -> dim_date`, `country_code -> dim_country`,
  `category_id -> dim_category`, `related_product_id -> dim_product`.

#### `fact_currency_rate`
- Daily FX rates by source.
- FK: `date_id -> dim_date`, `currency_code -> dim_currency`.

#### `fact_tariff`
- Tariff matrix by origin/destination + HS code.
- FK: `origin_country -> dim_country`, `destination_country -> dim_country`.

#### `fact_promo`
- Promotion campaigns.
- FK:
  - `listing_id -> fact_listing`
  - `marketplace_id -> dim_marketplace`
  - `start_date_id/end_date_id -> dim_date`
  - `category_id -> dim_category`

#### `fact_crypto_price`
- Daily crypto market data by symbol/source.
- FK: `date_id -> dim_date`.

#### `fact_commodity_price`
- Daily commodity prices by symbol/source.
- FK: `date_id -> dim_date`.

#### `fact_fuel_price`
- Daily retail fuel data by country/fuel type/source.
- FK: `date_id -> dim_date`, `country_code -> dim_country`, `currency_code -> dim_currency`.

### Operational app tables

#### `alerts`
- User alert definitions over products/listings/marketplaces/categories/countries.
- FK:
  - `user_id -> users.id`
  - optional: `product_id -> dim_product`, `listing_id -> fact_listing`,
    `marketplace_id -> dim_marketplace`, `category_id -> dim_category`,
    `country_code -> dim_country`.

#### `alert_events`
- Event history for alert triggers.
- FK: `alert_id -> alerts.id`, optional `listing_id -> fact_listing.id`.

#### `digests`
- Scheduled digest jobs per user.
- FK: `user_id -> users.id`.

#### `ai_chat_sessions`
- Chat sessions linked to user.
- FK: `user_id -> users.id`.

#### `ai_chat_messages`
- Message rows inside chat sessions.
- FK: `session_id -> ai_chat_sessions.id`.

#### `scrape_jobs`
- Parent job entity for scrape/discovery pipeline.
- FK: `marketplace_id -> dim_marketplace.id`, `triggered_by -> users.id`.
- `job_type` includes `full_pipeline_test`.

#### `scrape_logs`
- Per-listing scrape execution log rows.
- FK:
  - `scrape_job_id -> scrape_jobs.id`
  - `listing_id -> fact_listing.id`
  - `marketplace_id -> dim_marketplace.id`
- Status taxonomy currently includes:
  - `success`, `no_change`, `error`, `timeout`, `blocked`, `captcha`,
    `not_found`, `price_not_found`, `parse_error`, `missing_critical_data`,
    `technical_error`, `fetch_failed`, `parse_failed`, `quota_exceeded`,
    `persist_failed`.

#### `api_logs`
- API access log records.
- FK: optional `user_id -> users.id`.

#### `data_exports`
- Export jobs/files per user.
- FK: `user_id -> users.id`.

## Cross-table lifecycle notes

- Discovery writes:
  - `dim_marketplace` discovery fields
  - `dim_product` + `fact_listing` (URL-level entries)
- Scraping writes:
  - listing denormalized fields in `fact_listing`
  - snapshots in `fact_price`
  - diagnostics in `scrape_logs`
- Listing lifetime policy (migration 011 + service logic):
  - unchanged snapshots can be marked `no_change` without writing redundant `fact_price`
  - listings can be deactivated (`fact_listing.is_active = false`) after repeated errors
  - inactive listings are excluded from pool scrape selection query.

## Practical verification SQL (post-deploy)

```sql
SELECT COUNT(*) FROM fact_listing;
SELECT COUNT(*) FROM fact_price;
SELECT COUNT(*) FROM scrape_logs;
SELECT COUNT(*) FROM dim_product;
```

```sql
SELECT
  table_name,
  column_name,
  data_type
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position;
```

```sql
SELECT
  tc.table_name,
  kcu.column_name,
  ccu.table_name AS foreign_table_name,
  ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage ccu
  ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
ORDER BY tc.table_name, kcu.column_name;
```
