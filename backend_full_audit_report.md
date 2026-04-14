# Полный аудит backend (read-only)

## Актуализация (текущее состояние, 2026-04-04)

- **Git:** не добавлять в коммиты трейлеры `--trailer "Made-with: Cursor"` и аналоги.
- **Alembic head:** **`009_full_v2_schema_rebuild`** — идемпотентная полная DDL v2; предшествуют **`008`** (ширина **`alembic_meta.alembic_version.version_num`**), **`007`** (repair **`alembic_meta`**, таймауты, условный сброс пустого **`public`**), **`005`–`006`** (**`scrape_logs`**). **`alembic/env.py`:** **`await connection.commit()`** после **`run_sync`**. ORM: **`ScrapeLog.status` — `String(50)`**; каноника статусов — **`errors.SCRAPE_LOG_STATUSES`**.
- **Celery pool scrape:** `modules/scraper/tasks.py` — `_run_scrape_all_pool`, `scrape_pool_product`, `check_pool_completeness` используют **`sync_session_factory`**; **`GlobalScrapeService.scrape_product`** — синхронный `Session`; async только **`ScraperPool.scrape_product`** через **`_run_coro_in_worker`** в `service.py` (устранение `MissingGreenlet` в fork workers). При падении worker — **`_persist_technical_error_log`** пишет **`scrape_logs`** со статусом **`technical_error`** (если листинг найден).
- **`database.py`:** по-прежнему `async_session_maker` для FastAPI и **`sync_session_factory`** для workers; pool path — sync ORM.
- **`GlobalScrapeService` (`modules/scraper/service.py`):** при **`result.success`** сбрасываются **`listing.last_error`** и **`listing.consecutive_errors`**; при **`not result.success`** — инкремент **`consecutive_errors`** и **`last_error`**. **`fact_price`** пишется только при непустом **`product_name` или `title`**, **`price > 0`**, непустой **валюте**; **`dim_product.name`** при пустом `product_name` обновляется из **`title`**. **`_today_date_id`:** `SELECT` → **`INSERT … ON CONFLICT (date_id) DO NOTHING`** → `flush` → **`SELECT`** (идемпотентность, меньше deadlock при конкуренции за календарную строку). **`last_in_stock`:** `result.in_stock` → `data.in_stock` → **`False`**. Логи: **`EXTRACTED →`**, **`FINAL PERSIST`**, после успешного commit — **`SCRAPE COMPLETE listing_id=…`**, затем **`pool_scrape done`**.
- **`scrape_logs`:** колонка **`status` — String(50)** / в БД **`VARCHAR(50)`** (миграции **006**); CHECK включает **`missing_critical_data`**, **`price_not_found`**, **`technical_error`** и др. После деплоя — **`alembic upgrade head`** до **`009_full_v2_schema_rebuild`**.
- **Тесты (scraper):** `backend/tests/test_scraper_unit/` (unit, моки), `backend/tests/test_scraper_integration/`, `backend/tests/fixtures/scraper_fixtures.py`. Файлов **`test_scraper_persistence.py`** / **`test_scraper_extractors.py`** в корне `tests/` нет.
- См. также `Imperecta_Cursor_Project_Description.md`, `parsers_audit.md`, `imperecta_context.md`.

## Актуализация (архив, 2026-03-31)

### Миграции (head)
- Цепочка: `001` → … → `008` → **`009_full_v2_schema_rebuild` (head)**. Версия Alembic: **`alembic_meta.alembic_version`** (**`version_num` VARCHAR(255)**).
- `003`: additive колонки `users` + `pg_trgm`.
- `004`: drift repair (`users.plan` → `VARCHAR(20)`), cleanup legacy, при необходимости пересоздание app-таблиц, `pg_trgm`.
- `005`: идемпотентный CHECK `scrape_logs.status` + **`technical_error`**.
- `006`: **`scrape_logs.status` → `VARCHAR(50)`** (идемпотентно).
- `007`: repair **`alembic_meta`**, **`SET lock_timeout`/`statement_timeout`**, условный **`DROP SCHEMA public`** только для пустого `public`.
- `008`: **`version_num` → VARCHAR(255)**.
- `009`: идемпотентная полная DDL v2 (таблицы, партиции, MV, сиды).

### Celery
- `app/workers/celery_app.py`: `include` — `app.modules.scraper|alerts|digests|market_data.tasks`, `cleanup_tasks`, `maintenance_tasks`; broker SSL для `rediss://`; `backend=None`.
- `app/workers/scheduler.py`: **`celery_app.conf.beat_schedule = {}`** — периодический beat не ставит задачи в очередь до явного включения расписания.

### Кодовая база (актуальные пути)
- API и домены: только `backend/app/modules/*` (нет runtime `app/api/*`, `app/services/*`, `app/scrapers/*`).
- Парсинг: `modules/scraper/` — `discovery.py`, `scraper_pool.py`, `extractors.py`, `service.py`, `tasks.py`, `api.py`; файла `engine.py` в модуле нет.
- Admin pool/diagnostics: `modules/core/api_admin.py`. Scraper admin: `modules/scraper/api.py`.
- **Marketplaces admin:** `modules/marketplaces/service.py` (`MarketplaceService`) + `modules/marketplaces/api.py` — CRUD для `dim_marketplace` (список, add-by-url, импорт, удаление, квоты, `requires_js`, логи из `scrape_logs`). Исключение: **POST `/deduplicate`** пока без реализации merge дубликатов.

### Исторический блок ниже
- Разделы **2–16** содержат снимок аудита с путями вида `app/api/*`, `app/scrapers/engine.py`, `workers/scrape_tasks.py` — эта структура **удалена** или переименована. Для текущей архитектуры ориентируйтесь на этот раздел актуализации и на `Imperecta_Cursor_Project_Description.md`.

Дата актуализации верхнего блока: 2026-04-04

### Hotfix forced migration (2026-03-21) + meta repair (2026-04)
- В `backend/alembic/env.py` перед `run_migrations()`:
  - `CREATE SCHEMA IF NOT EXISTS alembic_meta` и **`CREATE TABLE IF NOT EXISTS alembic_meta.alembic_version`**;
  - проверка наличия `public.dim_date` как индикатора v2; при отсутствии — `DELETE FROM alembic_meta.alembic_version`;
  - при **пустой** версии и **наличии** `dim_date` — досев **`009_full_v2_schema_rebuild`** (восстановление после drift);
  - `context.configure(..., compare_type=True, render_item=...)`;
  - `connect_args["server_settings"]`: **`lock_timeout`** 10s, **`statement_timeout`** 60s (на Supabase также **`search_path`**).
- Риск "stamped head without DDL" снижен: guard + repair версии перед прогоном цепочки.

### Hotfix asyncpg statement safety (2026-03-21)
- В `backend/alembic/versions/001_v2_schema.py` добавлен SQL splitter `_split_sql_statements()` и обёртка `op.execute`, которая выполняет только одиночные SQL statements.
- Исправлен класс ошибок asyncpg: "cannot insert multiple commands into a prepared statement".
- Контракт миграции зафиксирован: один SQL statement на один execute даже при длинных SQL-блоках.

### Hotfix Celery Beat freeze (2026-03-21)
- В `backend/app/workers/scheduler.py` весь `celery_app.conf.beat_schedule` отключён через пустой dict: `celery_app.conf.beat_schedule = {}`.
- До завершения миграции и валидации parser stack не запускаются автоматические:
  - discovery/scraping задачи,
  - market ingestion (forex/crypto/commodities/fuel),
  - digests и maintenance jobs.
- Это предотвращает запись legacy/неконсистентных данных в новую v2 схему.

### Ключевой факт
- Backend в модульной структуре `backend/app/modules/*`. Legacy api/services/schemas/scrapers/notifications удалены как runtime.
- **PostgreSQL v2 (star schema):** базовые миграции `001_v2_schema` и `002_v2_additions` создают основную схему v2, затем corrective migrations `003_fix_users_columns` и `004_fix_real_state` устраняют production drift (missing users columns, enum/type legacy, coexistence legacy tables). Таблица версий Alembic: `alembic_meta.alembic_version` (`alembic/env.py`: `version_table_schema`). Спецификация: `Imperecta_Database_Schema_v2.md`.
- **ORM:** `app/models/core.py`, `dimensions.py`, `facts.py`, `app_tables.py`; реэкспорт в `models/__init__.py` (включая `FactCryptoPrice`, `FactCommodityPrice`, `FactFuelPrice`).

### Фактическая структура backend/app
- `common/`: deps.py, exceptions.py.
- `modules/core`, `modules/marketplaces`, `modules/scraper`, `modules/product_pool`, `modules/market_data`, `modules/dashboard`, `modules/user_products`, `modules/analytics`, `modules/alerts`, `modules/digests`, `modules/ai_analyst`.

### Роутеры
- В `main.py` только роутеры из `app.modules.*` под префиксом `/api`.
- Admin: `modules/core/api_admin.py` (prefix `/admin`), `modules/marketplaces/api.py` (prefix `/admin/marketplaces`), `modules/scraper/api.py` (prefix `/admin` для discovery, pool, scrape).

### Celery/Beat (дубль к разделу выше)
- `include` как в актуализации. Зарегистрированные задачи: `cleanup_old_data`, `refresh_materialized_views`, `ensure_fact_price_partitions`, модули `scraper|alerts|digests|market_data`. **Beat-расписание фактически пустое** (`scheduler.py`); перечисленные интервалы (MV, партиции, scrape, discovery, ingest, digests) применимы только после включения `beat_schedule`.

### Миграции
- Цепочка: `001` → … → **`009_full_v2_schema_rebuild` (head)**. Старая цепочка Alembic 001–016 из репозитория удалена.

### Изменения Fix Discovery/MarketData (2026-03-15)
- **Discovery:** `discover_all_marketplaces` dispatch'ит `discover_single_marketplace.delay(id)`. `extract_product_links` — строгая фильтрация: исключает /list/, /category/, /catalog/, /search; включает только product URLs (/\d{5,}, .html, /p/, /product/, 4+ сегментов). Batch commit + rollback recovery.
- **Scraping:** Decodo → httpx → Playwright. Price overflow: MAX_VALID_PRICE в scraper_pool и service; при overflow → discard. commit() try/except + rollback. _run_async: shutdown_asyncgens перед loop.close(). Celery: broker_connection_retry, broker_transport_options retry_policy.
- **Crypto:** Binance API primary (50 монет), CoinGecko backup. `BinanceCryptoAdapter`, `CryptoCompositeAdapter`.
- **Commodities:** 6 символов (XAU, XAG, XPT, XPD, WTI, BRENT). Отдельная задача `ingest_commodities` 4×/день. GET `/api/markets/commodities` из БД.
- **Admin:** GET `/api/admin/api-health`, GET `/api/admin/diagnostics/sample-products`, POST `/api/admin/products/cleanup-invalid`, POST `/api/admin/products/clear-pool` (v2 `fact_*`, `dim_marketplace`). Маркетплейсы: `MarketplaceService` + `/api/admin/marketplaces/*` (квоты, `requires_js`, импорт, логи); **POST `/deduplicate`** — без реализации слияния дубликатов.

### Изменения PR-1–PR-5
- **PR-1:** `/api/analytics/dashboard/summary` вызывает `DashboardService.get_kpi()` (метод `get_dashboard_summary` отсутствовал).
- **PR-2:** GET `/api/markets/overview` limit увеличен с 100 до 500.
- **PR-3:** Admin Page crash fix (frontend resilient к backend response format). Rate limits: `market_data/ingestion.py` — httpx.HTTPStatusError 429 → exponential backoff (attempt*30s). `market_data/service.py` — ALPHA_VANTAGE_TTL 4h (25 req/day free tier). `market_data/api.py` — GET `/api/markets/commodities` try/except → `{items:[], error}` без 500. Commodities widget: «Данные недоступны» при error.
- **PR-4:** Products page: две вкладки (пул + мои товары). GET `/api/pool/products` (search, marketplace_id, sort, limit, offset). Import: .csv, .tsv, .xls, .xlsx, .xlsm.
- **PR-5:** Admin pool: GET `/api/admin/diagnostics/pool`, POST `/api/admin/products/clear-user-data`, POST `/api/admin/marketplaces/recalculate-quotas`, POST `/api/admin/marketplaces/set-requires-js`. Discovery/trigger-all, pool/trigger-scrape в `modules/scraper/api.py`. AdminPage: секция «Управление пулом товаров» после «Активность парсинга»; human-readable diagnostics + raw JSON.
- **Decodo:** в `_fetch_html_decodo` (`scraper_pool`) проверка `decodo_enabled` и credentials; при отсутствии — skip и fallback (httpx/Playwright).

### Кросс-модульные зависимости
- Digests: `generate_digest` из `app.modules.ai_analyst.claude_client`.
- Decodo: только при `decodo_enabled` и заданных credentials.

### Статус файла
- Ниже — исторический аудит (разделы 1–16; пути `app/api/*`, `app/scrapers/*` устарели). Источник истины по текущей БД и ORM — блок «Актуализация (2026-03-31)» и `Imperecta_Database_Schema_v2.md`.

Дата снимка актуализации: 2026-04-04; исторические разделы ниже — более ранние.  
Режим: **только чтение**, без изменений кода.

---

## 1. Ядро приложения

### `backend/app/main.py`
- **Подключённые роутеры**: `admin_router` (core.api_admin), `auth_router`, `telegram_router`, `marketplaces_router`, `scraper_admin_router`, `pool_router`, `market_data_router`, `dashboard_router`, `products_router`, `competitors_router`, `import_router`, `analytics_router`, `alerts_router`, `digests_router`, `ai_router` — все под prefix `/api`.
- **Middleware**: `CORSMiddleware` (`L99-L105`), `allow_origins=settings.origins_list`.
- **Lifespan/startup**: в `lifespan()` запускаются фоновые задачи `create_all`, webhook Telegram, `ensure_superuser` (`L84-L90`).
- **Health endpoints**: `/health` и `/api/health` (`L115-L159`).
- **Потенциально мёртвое/спорное**:
  - дублирующее подключение роутеров (часть через `api_router`, часть напрямую в `main.py`) — архитектурно неоднородно.
  - явного закомментированного мёртвого кода в файле нет.

### `backend/app/config.py`
- **Env-поля (имя/type/default)**:
  - `database_url:str=postgresql+asyncpg://...`
  - `redis_url:str=redis://localhost:6379/0`
  - `jwt_secret:str=change-me-in-production`
  - `jwt_algorithm:str=HS256`
  - `jwt_expiration_minutes:int=30`
  - `jwt_refresh_expiration_days:int=7`
  - `jwt_refresh_expiration_days_remember:int=30`
  - `claude_api_key:str|None=None`
  - `market_data_forex_url:str=https://api.frankfurter.app/latest`
  - `market_data_crypto_url:str=https://api.coingecko.com/api/v3/coins/markets`
  - `market_data_commodities_url:str=""`
  - `goldapi_key:str=""`
  - `alpha_vantage_key:str=""`
  - `market_data_fuel_url:str=""`
  - `market_data_timeout_seconds:int=15`
  - `market_data_retry_attempts:int=3`
  - `claude_model:str=claude-sonnet-4-20250514`
  - `resend_api_key:str|None=None`
  - `email_from:str=noreply@imperecta.com`
  - `telegram_bot_token:str|None=None`
  - `telegram_webhook_secret:str|None=None`
  - `app_url:str=https://imperecta-production.up.railway.app`
  - `proxy_list:str=""`
  - `proxy_sticky_duration:int=10`
  - `proxy_country_routing:bool=True`
  - `decodo_api_url:str=https://scraper-api.decodo.com/v2/`
  - `decodo_username:str=""`
  - `decodo_password:str=""`
  - `decodo_enabled:bool=True`
  - `sentry_dsn:str=""`
  - `allowed_origins:str=http://localhost:5173,https://imperecta.pages.dev`
  - `app_env:str=development`
  - `port:int=8000`
  - `debug:bool=False`
- **Валидаторы**:
  - `database_url` должен быть `postgresql+asyncpg://` (`L49-L55`).
  - при `telegram_bot_token` обязателен `telegram_webhook_secret` (`L57-L65`).
- **Обязательные vs опциональные**:
  - технически почти всё имеет default -> формально не обязательно.
  - фактически для прод-режима обязательны `jwt_secret` (не дефолт), и при Telegram: обе переменные.
- **Подозрение на неиспользуемое**:
  - `port` не найден в backend-коде через `settings.port` (требует проверки на внешнем уровне запуска).

### `backend/app/database.py`
- **Async engine (API)**:
  - `create_async_engine(settings.database_url, ...)` (`L53`), `async_session_maker` (`L54-L60`), `get_db()` с commit/rollback (`L64-L73`).
- **Sync engine (Celery)**:
  - `_sync_url = replace(asyncpg -> postgresql)` (`L15`), `sync_engine=create_engine(...)` (`L16-L21`), `sync_session_factory` (`L22-L27`).
- **Разделение API vs Celery**:
  - API: `AsyncSession` через dependency.
  - Celery: sync `sessionmaker` + отдельные async factory в задачах, где нужно.

### Роутеры (main.py)
- Модульная архитектура: роутеры из `app.modules.*` под prefix `/api`. Нет единого `api_router` — каждый модуль подключается отдельно.

---

## 2. ORM-модели (текущее состояние — schema v2)

### `backend/app/models/__init__.py`
- Реэкспорт для Alembic `Base.metadata`: `User`, `UserSubscription`, `UserProduct`; `DimDate`, `DimCountry`, `DimCurrency`, `DimMarketplace`, `DimCategory`, `DimBrand`, `DimProduct`, `DimSeller`; `FactListing`, `FactPrice`, `FactReview`, `FactStock`, `FactSearchTrend`, `FactCurrencyRate`, `FactTariff`, `FactPromo`, `FactCryptoPrice`, `FactCommodityPrice`, `FactFuelPrice`; `Alert`, `AlertEvent`, `Digest`, `AIChatSession`, `AIChatMessage`, `ScrapeJob`, `ScrapeLog`, `ApiLog`, `DataExport`.

### `backend/app/models/core.py`
- Таблицы: `users` (расширенный профиль v2: `timezone`, `default_currency`, `telegram_username`, `is_active`, `last_login_ip`, `login_count`, **`preferences` JSONB** и т.д.), `user_subscriptions`, `user_products` (связь пользователь ↔ `dim_product` через `product_id`).

### `backend/app/models/dimensions.py`
- Таблицы: `dim_date`, `dim_currency`, `dim_country`, `dim_marketplace`, `dim_category`, `dim_brand`, `dim_product`, `dim_seller`. У **`dim_marketplace`** после миграции **002** — поля discovery/scraping (quota, pool, `requires_js`, задержки, custom CSS-селекторы, статусы last discovery).

### `backend/app/models/facts.py`
- Таблицы: `fact_listing` (**`url_hash`**, SHA256 дедупликация), `fact_price` (партиционирование на уровне БД), `fact_review`, `fact_stock`, `fact_search_trend`, `fact_currency_rate`, `fact_tariff`, `fact_promo`; **`fact_crypto_price`**, **`fact_commodity_price`**, **`fact_fuel_price`** (миграция 002).

### `backend/app/models/app_tables.py`
- Таблицы: `alerts`, `alert_events`, `digests`, `ai_chat_sessions`, `ai_chat_messages`, `scrape_jobs`, `scrape_logs`, `api_logs`, `data_exports`.

### Исторический снимок (до v2)
- Ниже в разделе «3. Pydantic schemas» и в старых заметках по файлам могут фигурировать пути `backend/app/api/*`, `models/product.py`, `products`, `competitor_products`, `global_products` — это **не** отражает текущую схему БД после `001_v2_schema` / `002_v2_additions`.

---

## 3. Pydantic schemas

**Актуально:** основные Pydantic-модели находятся в `backend/app/modules/*/schemas.py` (по доменам). Блок ниже описывает историческое расположение в плоском `app/schemas/*` — файлы могут отсутствовать или быть урезаны; сверяйте с репозиторием.

### `backend/app/schemas/__init__.py`
- Докстрока пакета (`"""Pydantic schemas."""`); доменные схемы — в `modules/*/schemas.py`.

### `backend/app/schemas/user.py`
- Классы: `UserRegister`, `UserLogin`, `UserResponse`, `UserUpdate`, `TokenResponse`, `ChangeInitialPasswordRequest`, `RefreshTokenRequest`, `TelegramLinkResponse` (`L33-L131`).
- Использование в API: **да**, в `api/auth.py` (`L17-L26`, декораторы `L56+`).

### `backend/app/schemas/product.py`
- Классы: `ProductCreate/Update/Response`, `ProductListItem/Response`, `CompetitorProductBrief`, `ProductDetailResponse` (`L10-L103`).
- Использование: **да**, `api/products.py` (`L13-L21`, response/request модели).

### `backend/app/schemas/competitor.py`
- Классы: `CompetitorCreate/Update/Response`, `CompetitorProductCreate/Response` (`L14-L79`).
- Использование: **да**, `api/competitors.py` (`L13-L19`).

### `backend/app/schemas/analytics.py`
- Классы: `PriceHistory*`, `Comparison*`, `SimulateRequest`, `AdvancedSimulationRequest` (`L10-L70`).
- Использование: **да**, `api/analytics.py` (`L20-L28`, response_model на `L33`, `L144`, body `L264`, `L281`).

### `backend/app/schemas/alert.py`
- Классы: `AlertCreate/Update/Response`, `AlertEventResponse`, `AlertExplanationResponse`, `AlertAutoResponseResponse` (`L10-L77`).
- Использование: **да**, `api/alerts.py` (`L11-L18`).

### `backend/app/schemas/digest.py`
- Класс: `DigestResponse` (`L9-L21`).
- Использование: **да**, `api/digests.py` (`L10`, `L15`, `L30`).

### `backend/app/schemas/ai_chat.py`
- Классы: `ChatRequest/Response`, `SessionListItem`, `MessageItem`, `SessionDetailResponse` (`L8-L52`).
- Использование: **да**, `api/ai.py` (`L11-L17`, response_model в декораторах).

### `backend/app/schemas/markets.py`
- Классы: `MarketsPreferences*`, `MarketsRefresh*`, `MarketsForex*`, `MarketsCrypto*`, `MarketsCommodities*`, `MarketsTicker*`, `MarketsOverview*`, `MarketsCategoryAnalytics*`, `MarketsMarketplaceAnalytics*`, `MarketsOpportunities*`.
- Использование:
  - **да**: почти все через `api/markets.py` import-блок (`L71-L83`) и response_model.
  - **нет (мёртвая схема)**: `MarketsOverviewItem`, `MarketsOverviewResponse` — упоминаний вне `schemas/markets.py` нет.

### `backend/app/schemas/global_product.py` (дополнительно)
- Классы: `GlobalProductResponse`, `GlobalProductListResponse`, `PoolCategorySummary`, `PoolStatsResponse`.
- Использование: **да**, `api/product_pool.py` (`response_model`).

---

## 4. API endpoints

### Зависимости `backend/app/api/deps.py`
- `DbSession`, `CurrentUser`, `CurrentSuperuser` (`L83-L97`).
- Auth делается через JWT Bearer + `decode_token` (`L18-L80`).

### Эндпоинты (метод + полный путь + auth)
- Модули: auth, telegram, products, competitors, analytics, alerts, digests, import, ai, dashboard, markets, pool, admin (core + marketplaces + scraper).
- Admin (superuser): `/api/admin/stats`, `/api/admin/users`, `/api/admin/claude-status`, `/api/admin/api-health`, `/api/admin/diagnostics/pool`, `/api/admin/products/cleanup-invalid`, `/api/admin/products/clear-user-data`, `/api/admin/products/clear-test-data`, `/api/admin/marketplaces/*` (включая deduplicate), `/api/admin/discovery/*`, `/api/admin/pool/trigger-scrape`, `/api/admin/trigger-scrape`, `/api/admin/scrape-activity`, `/api/admin/error-distribution`.

### Ключевые замечания
- `modules/core/api_admin.py`: prefix `/admin`, superuser-only. Endpoints: stats, users, claude-status, api-health, diagnostics/pool, products/cleanup-invalid, products/clear-user-data, products/clear-test-data.
- `modules/marketplaces/api.py`: prefix `/admin/marketplaces`. Endpoints: deduplicate (no-op merge), recalculate-quotas, set-requires-js, GET "", logs, POST "", add-by-url, import-file, import-text, DELETE. Нормализация URL и защита от дубликата по `domain` в `MarketplaceService.add_by_url`.
- `modules/scraper/api.py`: prefix `/admin`. Endpoints: discovery/trigger/{id}, discovery/trigger-all, pool/trigger-scrape, trigger-scrape, scrape-activity, error-distribution.
- В `api/markets.py` endpoint `/overview` уже читает из `ProductPoolService` (`L275-L300`).
- В `api/telegram.py` есть как webhook без user auth (`/webhook`), так и user endpoints через `get_current_user`.

---

## 5. Сервисы

### Файлы и статус
- `auth_service.py`: JWT/hash util; вызывается из `api/auth.py`, `api/deps.py`.
- `admin_service.py`: `ensure_superuser`; вызывается из `main.py` startup.
- `dashboard_service.py`: KPI/anomalies/trend; вызывается из `api/dashboard.py` и `api/analytics.py`.
- `price_service.py`: scrape helper; вызывается из `workers/scrape_tasks.py`.
- `benchmark_service.py`: benchmark/matrix; вызывается из `api/analytics.py`.
- `forecast_service.py`: forecast/simulations; вызывается из `api/analytics.py`.
- `import_service.py`: CSV/Excel parsing; вызывается из `api/import_export.py`.
- `ai_service.py`: digest generation; вызывается из `workers/digest_tasks.py`.
- `ai_chat_service.py`: chat sessions; вызывается из `api/ai.py`.
- `alert_ai_service.py`: explanation/autoresponse; вызывается из `api/alerts.py`, `workers/alert_tasks.py`.
- `product_ai_service.py`: categorization/recommendation; вызывается из `api/import_export.py`, `api/products.py`.
- `claude_monitor.py`: health/stats; вызывается из `api/admin.py`.
- `plan_limits.py`: limits wrappers; вызывается из `api/products.py`, `api/import_export.py`.
- `markets_service.py`: preferences/metadata/analytics/opportunities; вызывается из `api/markets.py`.
- `market_data_service.py`: external fetch/cache; вызывается из `api/markets.py`, providers.
- `seed_service.py`: **ФАЙЛ НЕ НАЙДЕН**.

### `services/market_data/*`
- `__init__.py`: реэкспорт DTO и ingestion service.
- `dto.py`: normalized DTO-классы.
- `ingestion_service.py`: ingestion + persist (upsert в `MarketsForex/Crypto/Commodity`, лог в `MarketsRefreshLog`).
- `aggregate_service.py`: materialization ticker/category/marketplace/opportunities.
- `providers/*`: BinanceCryptoAdapter (crypto primary), CryptoCompositeAdapter (Binance+CoinGecko), forex/crypto/commodities/fuel (+ GoldAPI/AlphaVantage).

### Методы с признаками мёртвого кода
- `ScraperFactory.register` (см. секция 13).
- `modules/core/api_admin.py`: нет legacy TLD_TO_COUNTRY / _domain_to_marketplace_id (удалены при рефакторинге).

---

## 6. Скрейперы

### `backend/app/scrapers/__init__.py`
- Экспортирует `BaseScraper`, `ScrapeResult`, `ScraperFactory`, `UniversalScraper`, `ProxyManager`, `proxy_manager`.

### `backend/app/scrapers/engine.py`
- `ScrapeResult` поля: `price`, `old_price`, `currency`, `product_name`, `image_url`, `description`, `in_stock`, `promo_label`, `product_url`, `extraction_method` (`L40-L54`).
- `BaseScraper` методы: `_get_proxy_country`, `_rate_limit`, `_random_delay`, `_backoff_delay`, `_scrape_impl(abstract)`, `scrape`.
- `UniversalScraper` pipeline:
  - Decodo-first (`_scrape_decodo`) -> JSON-LD/meta from returned HTML (`L175-L223`);
  - fallback `Playwright fetch` (`_fetch_page`) -> `_extract_jsonld` -> `_extract_meta` -> `_extract_dom_playwright` (`L140-L173`).
- `ScraperFactory`:
  - `create()` всегда возвращает `UniversalScraper` (`L438-L441`);
  - `register()` no-op (`L443-L446`).

### Методы `engine.py`: ИСПОЛЬЗУЕТСЯ / НЕ ИСПОЛЬЗУЕТСЯ
- Используются (внутри класса/файла и/или снаружи):
  - `BaseScraper.scrape` (через `price_service` -> `scraper.scrape(...)`).
  - `ScraperFactory.create` (через `price_service`).
  - `_scrape_impl`, `_scrape_decodo`, `_fetch_page`, `_extract_jsonld`, `_extract_meta`, `_extract_dom_playwright` — используются внутри flow `UniversalScraper`.
- Не используется:
  - `ScraperFactory.register` — внешних вызовов по проекту не найдено.

### `backend/app/scrapers/proxy_manager.py`
- Поддержка Decodo-прокси: rotating/sticky/geo-routing.
- Ключевые методы: `get_proxy`, `get_playwright_proxy`, `report_success/failure`, stats, sticky session manager.

---

## 7. Celery workers

### `backend/app/workers/celery_app.py`
- Broker: `settings.redis_url`.
- Result backend: `None`.
- Includes: `scrape_tasks`, `alert_tasks`, `digest_tasks`, `cleanup_tasks`, `market_data_tasks`, `discovery_tasks`.

### `backend/app/workers/scheduler.py` (Beat)
- Полный schedule на `L9-L42`:
  - `scrape_all` каждые 2ч.
  - weekly/daily digests.
  - cleanup weekly.
  - `ingest_market_data` каждые 2ч.
  - discovery/pool scraping/completeness tasks.

### Таски
- `scrape_tasks.py`
  - `scrape_single` (`name="scrape_single"`, `bind=True`, `max_retries=2`, timeout limits).
  - `scrape_user_products`.
  - `scrape_all` (`name="scrape_all"`).
  - Вызываются из API (`admin`, `competitors`) и Beat (`scrape_all`).
- `alert_tasks.py`
  - `check_alerts`, `generate_alert_ai_explanation`.
  - `check_alerts` вызывается из `scrape_single`.
- `digest_tasks.py`
  - `generate_weekly_digest`, `generate_daily_digest`, `schedule_weekly_digests`, `schedule_daily_digests`.
  - schedules вызываются Beat.
- `market_data_tasks.py`
  - `ingest_market_data` (`name="ingest_market_data", bind=True`) -> forex, crypto, fuel (без commodities).
  - `ingest_commodities` (`name="ingest_commodities", bind=True`) -> commodities 6 символов, 4×/день.
- `cleanup_tasks.py`
  - `cleanup_old_data` (`name="cleanup_old_data"`), запускается Beat.
- `discovery_tasks.py` (modules/scraper/tasks.py)
  - `discover_all_marketplaces`, `discover_single_marketplace(bind=True,max_retries=2)`,
  - `scrape_all_pool_products`,
  - `scrape_pool_product(bind=True,max_retries=1,soft_time_limit=120,time_limit=150)`,
  - `check_pool_completeness`.

---

## 8. Notifications

### `notifications/__init__.py`
- Только маркер/докстрока.

### `notifications/email_sender.py`
- Функции: `_md_to_html`, `send_alert_email`, `send_digest_email`, `send_alert_email_to_user`, `send_digest_email_to_user`.
- Использование:
  - из `workers/alert_tasks.py` (`send_alert_email_to_user`),
  - из `workers/digest_tasks.py` (`send_digest_email_to_user`).

### `notifications/telegram_bot.py`
- Функции: `send_message`, `send_price_alert`, `send_digest`, `send_out_of_stock_alert`, `send_promo_alert`.
- Использование:
  - из `api/telegram.py` (`send_message`),
  - из `workers/alert_tasks.py` (alert telegram sends),
  - из `workers/digest_tasks.py` (`send_digest`).

---

## 9. Entitlements

### `entitlements/plan.py`
- `ServiceTier`: `TRIAL`, `FREE`, `PAID_FULL`.
- `Feature`: `AI_ANALYST`.
- Таблицы соответствий:
  - `PLAN_TO_TIER`,
  - `FEATURE_ENTITLEMENTS`,
  - `USAGE_LIMITS`.
- Функции: `get_service_tier`, `is_trial/free/paid`, `is_trial_expired`, `has_feature`, `get_limit`, `get_entitlements_for_frontend`.

### `entitlements/__init__.py`
- Реэкспорт API entitlement-функций.

---

## 10. Alembic миграции

### `backend/alembic/env.py`
- Async migrations через `create_async_engine`, `target_metadata = Base.metadata`.
- `version_table_schema='alembic_meta'` (offline и online), чтобы версия переживала `DROP SCHEMA public CASCADE` в `001_v2_schema`.
- Перед `run_migrations`: `CREATE SCHEMA/TABLE` для **`alembic_meta.alembic_version`**, guard по **`dim_date`**, при пустой версии и наличии v2 — INSERT ревизии **`009_full_v2_schema_rebuild`** (drift repair); `context.configure(..., compare_type=True, render_item=...)`.
- После **`run_sync(do_run_migrations)`**: **`await connection.commit()`** — иначе DDL может откатиться при выходе из async-контекста.
- `connect_args["server_settings"]`: **`lock_timeout`** 10s, **`statement_timeout`** 60s; на Supabase — также **`search_path`**, SSL, отключение кеша prepared statements.
- Поддержка Supabase/PgBouncer connect args.

### `backend/alembic.ini`
- `sqlalchemy.url` из env / placeholder.

### `versions/001_v2_schema.py`
- Revision id: `001_v2_schema`, `down_revision = None` (новая цепочка).
- Создание схемы `alembic_meta` и перенос `alembic_version` из `public` при наличии.
- Destructive `upgrade`: temp backup `users`, `DROP SCHEMA public CASCADE`, `CREATE SCHEMA public`, grants, `CREATE EXTENSION` (pg_trgm, pgcrypto), все таблицы v2, индексы, seeds (`dim_date`, `dim_currency`, `dim_country`), materialized views с `WITH NO DATA`, восстановление строк `users`.
- `fact_price`: `PARTITION BY RANGE (date_id)` и партиции на 202601–202612.
- `downgrade`: `NotImplementedError`.

### `versions/002_v2_additions.py`
- Revision id: `002_v2_additions`, `down_revision = 001_v2_schema`.
- `CREATE TABLE` для `fact_crypto_price`, `fact_commodity_price`, `fact_fuel_price`; `ALTER TABLE` для `dim_marketplace`, `fact_listing`, `users`; `UPDATE dim_date` для `week_iso`; `DROP EXTENSION IF EXISTS jsonb_plperl`.
- `downgrade`: откат DROP/ALTER в обратном порядке.

### `003` → `009` (кратко)
- **`003_fix_users_columns`**, **`004_fix_real_state`** — additive/repair (см. актуализацию в начале файла).
- **`005_scrape_logs_technical_error`** — идемпотентное пересоздание `ck_scrape_logs_status` с **`technical_error`**.
- **`006_scrape_logs_status_length`** — `scrape_logs.status` → **`VARCHAR(50)`**.
- **`007_fix_migration_deadlock_and_meta`** — repair **`alembic_meta`**, таймауты DDL, условный сброс пустого **`public`**.
- **`008_fix_alembic_version_length`** — **`version_num` → VARCHAR(255)**.
- **`009_full_v2_schema_rebuild` (head)** — идемпотентная полная DDL v2 (таблицы, партиции, MV, сиды).

### Историческая цепочка (удалена из репозитория)
- Ранее существовали ревизии `001_initial_schema` … `016_drop_digest_summary_json`; при необходимости — только в истории git.

---

## 11. Тесты

### `backend/tests/conftest.py`
- Клиент: `httpx.AsyncClient` + `ASGITransport(app=app)` (`L30-L46`).
- БД: **реальная PostgreSQL test DB**, `DATABASE_URL=...imperecta_test` (`L11-L14`), не SQLite.
- Fixtures: `client`, `auth_headers`, `superuser_headers`.
- Mock/patch: в `conftest.py` нет.

### test_*.py (обзор; точные числа — в репозитории)
- Контрактные и security: `test_*_contract.py`, `test_health.py`, `test_security.py`, `test_telegram_webhook.py`, `test_marketplace_pool.py`, `test_product_pool_api.py`, `test_markets_contract.py`, `test_products_contract.py`, и др. в корне `backend/tests/`.
- **Scraper:** пакеты **`test_scraper_unit/`** и **`test_scraper_integration/`**, фикстуры **`fixtures/scraper_fixtures.py`** (замена устаревших `test_scraper_persistence.py` / `test_scraper_extractors.py`).

### Mock/patch/MagicMock/monkeypatch
- `monkeypatch` в `test_telegram_webhook.py`.
- `test_scraper_unit/`: **`MagicMock`**, **`monkeypatch`** для sync `Session`, `ScraperPool`, `_run_coro_in_worker`, `_today_date_id`; интеграционные сценарии в `test_scraper_integration/` при доступной БД.

### Тесты на удалённый функционал
- Прямых тестов на `seed_service.py` или `markets_overview.py` не обнаружено.
- Есть legacy-инъекционный кейс по `sort` со строкой `DROP TABLE markets_overview` в `test_security.py` (`L472-L478`) — это проверка валидации параметра, не реальный вызов модели.

---

## 12. Инфраструктура

### `backend/Dockerfile`
- Base: `python:3.12-slim`.
- Установка зависимостей + `playwright install --with-deps chromium`.
- CMD: `alembic upgrade head && uvicorn app.main:app ...` (`L29`).

### `backend/requirements.txt`
- Ключевые: FastAPI/Uvicorn/SQLAlchemy/Alembic/Celery/Redis/Anthropic/Playwright/BS4/pandas/pytest.
- Есть security tooling (`safety`, `pip-audit`, `bandit`) и pinned deps.

### `backend/pyproject.toml`
- Ruff включён (`tool.ruff`), lint rules `E,F,I,N,W`.
- Pytest: `asyncio_mode=auto`, `testpaths=["tests"]`.

### `docker-compose.yml`
- Сервисы: `postgres`, `redis`, `backend`, `celery-worker`, `celery-beat`, `frontend`.
- Volumes: `postgres_data`, bind mount `./backend/app:/app/app`.

---

## 13. Мёртвый код — сводная таблица

| Файл | Элемент | Тип | Доказательство |
|---|---|---|---|
| `backend/app/modules/core/api_admin.py` | — | Актуален: stats, users, claude-status, diagnostics/pool, products/clear-user-data | — |
| `backend/app/scrapers/engine.py` | `ScraperFactory.register()` | Метод без вызовов | поиском `ScraperFactory.register(` совпадений нет |
| `backend/app/schemas/markets.py` | `MarketsOverviewItem` | Схема не используется endpoint-ами | встречается только в `schemas/markets.py` |
| `backend/app/schemas/markets.py` | `MarketsOverviewResponse` | Схема не используется endpoint-ами | встречается только в `schemas/markets.py` |
| `backend/app/models/markets_overview.py` | весь файл | Удалён/отсутствует | **ФАЙЛ НЕ НАЙДЕН** |
| `backend/app/services/seed_service.py` | весь файл | Удалён/отсутствует | **ФАЙЛ НЕ НАЙДЕН** |
| `backend/app/config.py` | `port` | Потенциально не читается в backend-коде | не найдено `settings.port` (требует проверки запуска) |

---

## 14. Граф зависимостей модулей

### API -> Services
- `api/auth` -> `auth_service`
- `api/products` -> `plan_limits`, `product_ai_service`
- `api/competitors` -> (без отдельного service, прямой ORM + worker trigger)
- `api/analytics` -> `forecast_service`, `benchmark_service`, `dashboard_service`
- `api/dashboard` -> `dashboard_service`
- `api/alerts` -> `alert_ai_service`
- `api/import_export` -> `import_service`, `plan_limits`, `product_ai_service`
- `api/ai` -> `ai_chat_service`
- `api/markets` -> `market_data_service`, `markets_service`, `product_pool_service`
- `api/admin` (core.api_admin, marketplaces.api, scraper.api) -> `claude_monitor`, `MarketplacePoolService`
- `api/product_pool` -> `product_pool_service`
- `api/deps` -> `auth_service`

### Services -> Models
- Большинство сервисов импортируют ORM-модели напрямую (`Product`, `Competitor*`, `Markets*`, `GlobalProduct*`, `ApiLog`, и т.д.).

### Workers -> Services
- `scrape_tasks` -> `price_service`
- `market_data_tasks` -> `market_data.ingestion_service`, `market_data.aggregate_service`
- `alert_tasks` -> `alert_ai_service`
- `digest_tasks` -> `ai_service`
- `discovery_tasks` -> `global_scrape_service`

### Циклические зависимости
- Явного жёсткого import-cycle уровня модуля не обнаружено по прочитанным файлам.  
- Возможны мягкие runtime-циклы через ленивые импорты внутри функций (`ТРЕБУЕТ ПРОВЕРКИ` при глубокой статической проверке).

---

## 15. Критические риски/замечания

- Admin endpoints в `modules/core/api_admin.py` — без сид-данных. Диагностика pool через raw SQL к admin_marketplaces, global_products, discovery_logs.
- Архитектура роутеров смешанная: часть через `api_router`, часть напрямую в `main.py`.
- В `markets` схемах остались legacy `MarketsOverview*`, но `/markets/overview` возвращает plain `dict` из pool-сервиса.
- `market_data_service.py` содержит large static `FUEL_PRICES` блок (если требование только real data — это риск расхождения).

---

## 16. Вывод

- Backend в рабочем состоянии как многомодульная система: FastAPI + Celery + ORM + scraper stack + market data ingestion + pool/discovery.
- Основные зоны технического долга: legacy схемы/хардкоды в admin/markets и несколько неиспользуемых элементов.
- Для строгой финализации аудита рекомендован второй проход с автоматизированным статанализом (`ruff/pyright/call graph`) в рабочем окружении, где доступны все dev-зависимости.

