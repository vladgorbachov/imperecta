# Полный аудит backend (read-only)

## Актуализация (после PR-7 и PR-1–PR-5)

Дата актуализации: 2026-03-15

### Ключевой факт
- Backend в модульной структуре `backend/app/modules/*`. Legacy api/services/schemas/scrapers/notifications удалены как runtime.

### Фактическая структура backend/app
- `common/`: deps.py, exceptions.py.
- `modules/core`, `modules/marketplaces`, `modules/scraper`, `modules/product_pool`, `modules/market_data`, `modules/dashboard`, `modules/user_products`, `modules/analytics`, `modules/alerts`, `modules/digests`, `modules/ai_analyst`.

### Роутеры
- В `main.py` только роутеры из `app.modules.*` под префиксом `/api`.
- Admin: `modules/core/api_admin.py` (prefix `/admin`), `modules/marketplaces/api.py` (prefix `/admin/marketplaces`), `modules/scraper/api.py` (prefix `/admin` для discovery, pool, scrape).

### Celery/Beat
- `celery_app.conf.include`: scraper, alerts, digests, market_data. `cleanup_old_data` в `app.workers.cleanup_tasks`. Beat: scrape_all, discover_all_marketplaces, scrape_all_pool_products, check_pool_completeness, ingest_market_data, cleanup, digests (weekly/daily).

### Миграции
- 015 = `015_global_products`, 016 = `016_drop_digest_summary_json`.

### Изменения PR-1–PR-5
- **PR-1:** `/api/analytics/dashboard/summary` вызывает `DashboardService.get_kpi()` (метод `get_dashboard_summary` отсутствовал).
- **PR-2:** GET `/api/markets/overview` limit увеличен с 100 до 500.
- **PR-3:** Admin Page crash fix (frontend resilient к backend response format). Rate limits: `market_data/ingestion.py` — httpx.HTTPStatusError 429 → exponential backoff (attempt*30s). `market_data/service.py` — ALPHA_VANTAGE_TTL 4h (25 req/day free tier). `market_data/api.py` — GET `/api/markets/commodities` try/except → `{items:[], error}` без 500. Commodities widget: «Данные недоступны» при error.
- **PR-4:** Products page: две вкладки (пул + мои товары). GET `/api/pool/products` (search, marketplace_id, sort, limit, offset). Import: .csv, .tsv, .xls, .xlsx, .xlsm.
- **PR-5:** Admin pool: GET `/api/admin/diagnostics/pool`, POST `/api/admin/products/clear-user-data`, POST `/api/admin/marketplaces/recalculate-quotas`, POST `/api/admin/marketplaces/set-requires-js`. Discovery/trigger-all, pool/trigger-scrape в `modules/scraper/api.py`. AdminPage: секция «Управление пулом товаров» после «Активность парсинга»; human-readable diagnostics + raw JSON.
- **Decodo:** в `_fetch_html_decodo` (scraper_pool) и `_scrape_decodo` (engine) проверка `decodo_enabled` и наличие username/password; при отсутствии — skip и fallback (httpx/Playwright).

### Кросс-модульные зависимости
- Digests: `generate_digest` из `app.modules.ai_analyst.claude_client`.
- Decodo: только при `decodo_enabled` и заданных credentials.

### Статус файла
- Ниже — исторический аудит. Источник истины — этот блок «Актуализация».

Дата: 2026-03-15  
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

## 2. ORM-модели

### `backend/app/models/__init__.py`
- Импортируются: `AdminMarketplace`, `AIChat*`, `Alert*`, `ApiLog`, `Competitor*`, `Digest`, `DiscoveryLog`, `GlobalProduct*`, `Markets*`, `PriceSnapshot`, `Product`, `ScrapeLog`, `User` (`L3-L61`).

### `backend/app/models/admin_marketplace.py`
- Таблица: `admin_marketplaces` (`L15`).
- Колонки: `id`, `marketplace_id(unique)`, `name`, `domain`, `base_url`, `country`, `region`, `currency`, `scraper_type`, `is_active`, scrape counters/status fields, pool/quota fields, custom selectors, discovery settings, `created_at` (`L17-L61`).
- Relationship: не объявлены явно в файле (backref задаётся в `global_product.py`).
- Индексы: явных `Index(...)` нет.

### `backend/app/models/product.py`
- Таблица: `products` (`L18`).
- Индекс: `ix_products_user_id` (`L19`).
- FK: `user_id -> users.id` (`L26-L30`).
- Relationships: `user`, `competitor_products`, `alerts` (`L50-L59`).

### `backend/app/models/competitor.py`
- Таблица: `competitors` (`L17`), индекс `ix_competitors_user_id` (`L18`).
- FK: `user_id -> users.id` (`L25-L29`).
- Relationships: `user`, `competitor_products` (`L43-L48`).

### `backend/app/models/competitor_product.py`
- Таблица: `competitor_products` (`L18`), индекс `ix_competitor_products_product_id` (`L19`).
- FK: `product_id -> products.id`, `competitor_id -> competitors.id` (`L26-L35`).
- Relationships: `product`, `competitor`, `price_snapshots`, `alert_events` (`L58-L71`).

### `backend/app/models/price_snapshot.py`
- Таблица: `price_snapshots` (`L18`).
- Индексы: `ix_snapshots_cp_date`, `ix_snapshots_date` (`L19-L22`).
- FK: `competitor_product_id -> competitor_products.id` (`L29-L33`).
- Relationship: `competitor_product` (`L44-L47`).

### `backend/app/models/user.py`
- Таблица: `users` (`L27`), email unique+index (`L34`).
- Enum: `UserPlan` (`L15-L22`).
- Relationships: `products`, `competitors`, `alerts`, `digests`, `markets_preferences` (`L72-L97`).

### `backend/app/models/alert.py`
- Таблица: `alerts` (`L18`).
- FK: `user_id -> users.id`, `product_id -> products.id` (`L25-L34`).
- Relationships: `user`, `product`, `alert_events` (`L55-L64`).

### `backend/app/models/alert_event.py`
- Таблица: `alert_events` (`L18`).
- Индексы: `ix_alert_events_triggered`, `ix_alert_events_alert_triggered` (`L19-L22`).
- FK: `alert_id -> alerts.id`, `competitor_product_id -> competitor_products.id` (`L29-L38`).
- Relationships: `alert`, `competitor_product` (`L53-L57`).

### `backend/app/models/digest.py`
- Таблица: `digests` (`L17`), FK `user_id -> users.id` (`L24-L28`), relationship `user` (`L54`).
- Пометка в комментарии: `summary_json` отмечен как `UNUSED` (`L42-L43`).

### `backend/app/models/ai_chat.py`
- Таблицы: `ai_chat_sessions`, `ai_chat_messages` (`L17`, `L55`).
- Индекс: `ix_chat_messages_session` (`L56-L58`).
- FK: session.user_id -> users, message.session_id -> ai_chat_sessions (`L20-L25`, `L61-L66`).
- Relationship: session.messages, message.session (`L44-L49`, `L77-L80`).

### `backend/app/models/scrape_log.py`
- Таблица: `scrape_logs` (`L18`).
- Индексы: `ix_scrape_logs_mp_date`, `ix_scrape_logs_status`, plus `marketplace_id` and `created_at` indexes via columns (`L19-L22`, `L25`, `L41`).
- FK: `competitor_product_id -> competitor_products.id` (`L27-L31`).

### `backend/app/models/api_log.py`
- Таблица: `api_logs` (`L15`), индекс `ix_api_logs_service_date` (`L16-L18`), `service` and `created_at` индексируются также на колонках.

### `backend/app/models/markets_overview.py`
- **ФАЙЛ НЕ НАЙДЕН**.

### `backend/app/models/markets_analytics.py`
- Таблицы: `markets_category_analytics`, `markets_marketplace_analytics` (`L17`, `L41`).
- Индексы: `ix_markets_category_*`, `ix_markets_marketplace_*` (`L18-L21`, `L42-L45`).

### `backend/app/models/markets_opportunity.py`
- Таблица: `markets_opportunities` (`L17`), индексы `ix_markets_opportunities_*` (`L18-L21`).

### `backend/app/models/markets_preferences.py`
- Таблица: `markets_preferences` (`L17`), FK `user_id -> users.id` (`L19-L23`), relationship `user` (`L45`).

### `backend/app/models/markets_refresh_log.py`
- Таблица: `markets_refresh_log` (`L39`).
- Enums: `MarketsRefreshType`, `MarketsRefreshStatus` (`L13-L34`).
- Колонки метаданных refresh: provider/country/error (`L64-L67`).

### `backend/app/models/markets_snapshots.py`
- Таблицы: `markets_forex`, `markets_crypto`, `markets_commodities`, `markets_ticker` (`L15`, `L34`, `L52`, `L71`).
- Для каждой таблицы есть unique индекс по `symbol` (`L16`, `L35`, `L53`, `L72`).

---

## 3. Pydantic schemas

### `backend/app/schemas/__init__.py`
- Только докстрока (`L1`).

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
- Admin (superuser): `/api/admin/stats`, `/api/admin/users`, `/api/admin/claude-status`, `/api/admin/diagnostics/pool`, `/api/admin/products/clear-user-data`, `/api/admin/products/clear-test-data`, `/api/admin/marketplaces/*`, `/api/admin/discovery/*`, `/api/admin/pool/trigger-scrape`, `/api/admin/trigger-scrape`, `/api/admin/scrape-activity`, `/api/admin/error-distribution`.

### Ключевые замечания
- `modules/core/api_admin.py`: prefix `/admin`, superuser-only через `dependencies=[Depends(get_current_superuser)]`. Endpoints: stats, users, claude-status, diagnostics/pool, products/clear-user-data, products/clear-test-data.
- `modules/marketplaces/api.py`: prefix `/admin/marketplaces`. Endpoints: recalculate-quotas, set-requires-js, GET "", logs, POST "", add-by-url, import-file, DELETE.
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
- `providers/*`: адаптеры forex/crypto/commodities/fuel (+ GoldAPI/AlphaVantage adapter).

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
  - `ingest_market_data` (`name="ingest_market_data", bind=True`) -> ingestion + aggregate pipeline.
- `cleanup_tasks.py`
  - `cleanup_old_data` (`name="cleanup_old_data"`), запускается Beat.
- `discovery_tasks.py`
  - `discover_all_marketplaces`, `discover_single_marketplace(bind=True,max_retries=2)`,
  - `scrape_all_pool_products`,
  - `scrape_pool_product(bind=True,max_retries=1)`,
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
- Async migrations через `create_async_engine` (`L72-L105`), `target_metadata = Base.metadata` (`L48`).
- Поддержка Supabase/PgBouncer connect args.

### `backend/alembic.ini`
- `sqlalchemy.url = postgresql+asyncpg://...` (`L6`).

### `versions/*`
- `001_initial_schema.py`: no-op (ожидает create_all).
- `002_update_user_language_default.py`: users.language type/default.
- `003_telegram_user_fields.py`: уникальность `telegram_chat_id`, resize `telegram_link_code`.
- `004_add_superuser_scrape_logs_admin_marketplaces_api_logs.py`: users fields + `scrape_logs`, `admin_marketplaces`, `api_logs`.
- `005_add_user_last_login_at.py`: users.last_login_at.
- `006_add_ai_chat_tables.py`: `ai_chat_sessions`, `ai_chat_messages`.
- `007_add_performance_indexes.py`: performance indexes.
- `007_add_alert_ai_fields.py`: AI-поля в `alert_events`.
- `008_add_digest_type_ai_tone.py`: users.ai_tone + widen digest period type.
- `009_add_user_avatar_url.py`: avatar_url.
- `010_extend_avatar_url_for_data_urls.py`: avatar_url -> Text.
- `011_reset_trial_ends_at.py`: reset trial_ends_at.
- `012_add_markets_tables.py`: markets_* tables + enums.
- `013_markets_refresh_log_metadata.py`: refresh metadata columns + enum fuel.
- `014_avatar_url_text_preferred_country.py`: pass/no-op migration.
- `015_add_global_products_and_extend_marketplaces.py`: extend admin_marketplaces, create `global_products`, `global_price_snapshots`, `discovery_logs`.

### Дубликат номера ревизии
- Есть два файла с префиксом `007_...`, но **`revision` id разные**:
  - `007_performance_indexes`
  - `007_alert_ai_fields`
- Цепочка валидна (`007_alert_ai_fields` ссылается на `007_performance_indexes`).

---

## 11. Тесты

### `backend/tests/conftest.py`
- Клиент: `httpx.AsyncClient` + `ASGITransport(app=app)` (`L30-L46`).
- БД: **реальная PostgreSQL test DB**, `DATABASE_URL=...imperecta_test` (`L11-L14`), не SQLite.
- Fixtures: `client`, `auth_headers`, `superuser_headers`.
- Mock/patch: в `conftest.py` нет.

### test_*.py (кол-во тестов / mock usage)
- `test_admin_contract.py`: 3.
- `test_ai_contract.py`: 2.
- `test_analytics_contract.py`: 3.
- `test_auth_contract.py`: 8.
- `test_dashboard_contract.py`: 3.
- `test_health.py`: 1.
- `test_markets_contract.py`: 7.
- `test_marketplace_pool.py`: 7.
- `test_product_pool_api.py`: 5.
- `test_products_contract.py`: 4.
- `test_scraper_extractors.py`: 8.
- `test_security.py`: 28.
- `test_telegram_webhook.py`: 5.

### Mock/patch/MagicMock/monkeypatch
- Найден только `monkeypatch` в `test_telegram_webhook.py` (`L11+`, `L25+`, `L40+`, `L55+`).
- `MagicMock`/`AsyncMock`/`patch` в test_*.py не найдены.

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

