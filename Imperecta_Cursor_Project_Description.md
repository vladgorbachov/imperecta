# Imperecta — Описание проекта для Cursor IDE

## Актуализация (текущее состояние, 2026-04-01)

- **Git / коммиты:** запрещено добавлять в коммиты трейлеры вида `--trailer "Made-with: Cursor"` и любые аналогичные метки «сделано ассистентом»; сообщения коммитов — обычные, без таких трейлеров.
- **Pool scrape в Celery (greenlet / MissingGreenlet):** путь `scrape_all_pool_products` / `scrape_all` / `scrape_pool_product` / `check_pool_completeness` использует **`sync_session_factory` + psycopg2** из `database.py` для ORM; **`GlobalScrapeService.scrape_product`** — **синхронный `Session`**. Асинхронный **`ScraperPool.scrape_product`** вызывается через **`_run_coro_in_worker`** (отдельный event loop на вызов). Discovery-задачи по-прежнему через локальный async engine + `_run_async`.
- **`ExtractedProduct`:** поля `title`, `price`, `currency`, … — **нет `in_stock`**; наличие на складе берётся через **`getattr`/optional**, без хардкода `True`.
- **`scrape_logs.status`:** колонка расширена до **VARCHAR(32)**; в CHECK добавлено **`missing_critical_data`**; при успешном scrape с данными: нет title → `missing_critical_data`, есть title но `price is None` → `price_not_found`; debug-лог после пула: product_name/price/currency/in_stock/fields_extracted; при пропуске `fact_price` из‑за отсутствия названия или валюты — `logger.info` с текстом про skip.
- **`fact_price`:** пишется только при **непустом названии (title)**, **price > 0** и **непустой валюте**; `scrape_logs` пишется на каждую попытку (при существующем листинге).

## Актуализация (архив, 2026-03-31)

- **Alembic chain (actual head):** `001_v2_schema` → `002_v2_additions` → `003_fix_users_columns` → `004_fix_real_state` (head). Файл `004_fix_real_state.py` добавляет repair-слой для production-состояния БД: приведение `users.plan` к `VARCHAR(20)`, удаление legacy tables/types/sequences, доинициализация app-таблиц v2, повторная гарантия `pg_trgm`.
- **Parser runtime cleanup (2026-03-24):** `backend/app/modules/scraper/engine.py` удалён из production runtime path. Каноничный путь: `tasks -> discovery/service -> scraper_pool -> extractors`.
- **Parser contracts (2026-03-24):** `PoolScrapeResult` расширен quality-полями (`is_partial`, `is_empty`, `fields_extracted`, `fields_missing`), `discover()` в `discovery.py` возвращает `DiscoveryResult` dataclass.
- **Persistence hardening (2026-03-24):** в `scraper/service.py` удалены фейковые дефолты (`USD`, `in_stock=True`), `fact_price` пишется только при наличии currency, и добавлена обязательная запись в `scrape_logs` после каждой попытки scrape.
- **Migration hardening:** в `backend/alembic/env.py` используется guard по фактическому наличию `dim_date` + проверка `alembic_meta.alembic_version` перед reset; в `001_v2_schema.py` используется `_split_sql_statements` + безопасный `op.execute` wrapper для asyncpg (один SQL statement на один execute).
- **Users migration path:** `001_v2_schema.py` сохраняет backup пользователей с `plan::text`, далее restore users в новую таблицу; `003` и `004` закрывают случаи, когда БД осталась в смешанном legacy/v2 состоянии.
- **Marketplace migration policy:** backup/restore `admin_marketplaces` из `001_v2_schema.py` удалён. Миграция 001 больше переносит только users; строки `dim_marketplace` создаются через админ-API / импорт (не сиды в коде).
- **Marketplaces admin API:** `modules/marketplaces/service.py` — `MarketplaceService` (CRUD для `dim_marketplace`): список, `add_by_url`, `import_from_text`, удаление, `update_marketplace` (в т.ч. `requires_js`), `recalculate_quotas`. `modules/marketplaces/api.py`: GET список (ответ в формате админ-UI), POST `/` и `/add-by-url`, POST `/import-file`, `/import-text`, DELETE по UUID, `/recalculate-quotas`, `/set-requires-js`, GET `/{id}/logs` (из `scrape_logs`). **POST `/deduplicate`** — пока без реализации дедупликации (возвращает сообщение, не 501). Диагностика пула и cleanup — по-прежнему `core/api_admin` и `scraper/api`. **GET `/api/competitors/marketplaces`** — список имён из `dim_marketplace` через `MarketplaceService`.
- **Celery Beat status:** в `backend/app/workers/scheduler.py` расписание жёстко отключено: `celery_app.conf.beat_schedule = {}` (не закомментированный словарь задач, а пустой dict).
- **DB reality vs old notes:** более ранние блоки в документе ниже содержат часть устаревших формулировок (например, где head указан как `002_v2_additions`); источником истины считать этот раздел актуализации + текущие файлы миграций `003`/`004`.

- **Hotfix forced migration (2026-03-21):** в `backend/alembic/env.py` добавлена защитная проверка фактического применения v2 перед `run_migrations()`. Если таблица `public.dim_date` отсутствует (случай stamped head без реального DDL), выполняется `DELETE FROM alembic_meta.alembic_version`, после чего миграции `001_v2_schema` и `002_v2_additions` запускаются повторно. В `context.configure(...)` включён `compare_type=True`.
- **Hotfix asyncpg statement safety (2026-03-21):** в `backend/alembic/versions/001_v2_schema.py` добавлен `_split_sql_statements()` и безопасная обёртка `op.execute`, которая разбивает SQL-батчи на отдельные statements. Это устраняет ошибки asyncpg вида "cannot insert multiple commands into a prepared statement" и гарантирует правило: один SQL statement на один execute.
- **Hotfix Celery Beat freeze (2026-03-21):** в `backend/app/workers/scheduler.py` установлен пустой scheduler (`celery_app.conf.beat_schedule = {}`). Автоматический discovery/scraping/ingestion/digests/maintenance не запускается до поэтапной валидации парсеров на v2.

- **База данных (PostgreSQL star schema v2):** полная пересборка миграцией `001_v2_schema`. Перед `DROP SCHEMA public CASCADE` версия Alembic хранится в `alembic_meta.alembic_version` (`alembic/env.py`: `version_table_schema='alembic_meta'`). Данные `users` бэкапятся во временную таблицу и восстанавливаются после создания схемы. Расширения `pg_trgm`, `pgcrypto`. Измерения: `dim_date`, `dim_currency`, `dim_country`, `dim_marketplace`, `dim_category`, `dim_brand`, `dim_product`, `dim_seller`. Факты: `fact_listing`, `fact_price` (партиции по `date_id` на 202601–202612), `fact_review`, `fact_stock`, `fact_search_trend`, `fact_currency_rate`, `fact_tariff`, `fact_promo`. Приложение: `users`, `user_subscriptions`, `user_products`, `alerts`, `alert_events`, `digests`, `ai_chat_sessions` / `ai_chat_messages`, `scrape_jobs`, `scrape_logs`, `api_logs`, `data_exports`. Seeds: `dim_date` (2024–2030), `dim_currency` (включая ISK, BAM, MKD, ALL и др.), `dim_country` (40+). Materialized views: `mv_daily_price_summary`, `mv_marketplace_health` (`WITH NO DATA`). Спецификация: `Imperecta_Database_Schema_v2.md`.
- **Миграция `002_v2_additions` (base additions):** без DROP данных — `fact_crypto_price`, `fact_commodity_price`, `fact_fuel_price`; в `dim_marketplace` — поля discovery/scraping (quota, `products_in_pool`, `requires_js`, `rate_limit_delay`, custom CSS-селекторы, статусы last discovery); в `fact_listing` — `url_hash` (уникальный индекс, дедупликация URL); в `users` — `preferences` (JSONB, вместо legacy `markets_preferences`); исправление `dim_date.week_iso` через `EXTRACT(WEEK FROM full_date)`; `DROP EXTENSION IF EXISTS jsonb_plperl` (Supabase).
- **ORM:** `backend/app/models/core.py`, `dimensions.py`, `facts.py`, `app_tables.py`; единый реэкспорт в `models/__init__.py` для Alembic metadata.
- Backend в модульной архитектуре `backend/app/modules/*`. Роутеры из `modules/*` под префиксом `/api` в `main.py`.
- **Alembic:** цепочка `001_v2_schema` → `002_v2_additions` → `003_fix_users_columns` → `004_fix_real_state` (head); старая цепочка 001–016 из репозитория удалена.
- **Digests:** `generate_digest` из `app.modules.ai_analyst.claude_client`.
- **Celery:** `celery_app.conf.include`: `app.modules.scraper|alerts|digests|market_data.tasks`, `app.workers.cleanup_tasks`, `app.workers.maintenance_tasks`. Задачи обслуживания (ручной/будущий beat): `refresh_materialized_views`, `ensure_fact_price_partitions`. **Beat сейчас:** `celery_app.conf.beat_schedule = {}` в `scheduler.py` — периодические задачи не ставятся в очередь автоматически; целевые интервалы (MV :15, партиции 1-го числа, scrape/discovery/ingest/digests) применимы только после явного включения расписания.
- **Decodo:** в `scraper/scraper_pool.py` — Decodo → httpx → Playwright; после успешного Decodo HTML не перезапрашивается. `scrape_pool_product` soft_time_limit=120, time_limit=150. **Price overflow:** MAX_VALID_PRICE=9_999_999_999.99 в scraper_pool и service; при overflow → price=None, discard. commit() в try/except с rollback. **_run_async:** shutdown_asyncgens перед loop.close() (Event loop is closed). **Celery:** broker_connection_retry, broker_transport_options retry_policy.
- **Discovery:** двухуровневый: Level 1 — поиск URL категорий (homepage/sitemap); Level 2 — для каждой категории `extract_product_links` → URL товаров. Каждый URL товара = отдельная запись GlobalProduct. `extract_product_links` — строгая фильтрация: исключает /list/, /category/, /catalog/, /search, короткие пути; включает только product URLs (/\d{5,}, .html, /p/, /product/, 4+ сегментов). `discover_all_marketplaces` dispatch'ит `discover_single_marketplace.delay(id)` — каждая с fresh DB session. Batch commit каждые 50 записей + rollback recovery. POST `/api/admin/products/cleanup-invalid`, POST `/api/admin/products/clear-pool`, GET `/api/admin/diagnostics/sample-products`.
- **Crypto:** Binance API primary (50 монет), CoinGecko backup. `CryptoCompositeAdapter`, `BinanceCryptoAdapter`.
- **Commodities:** 6 символов (XAU, XAG, XPT, XPD, WTI, BRENT). Отдельная задача `ingest_commodities` 4×/день. GET `/api/markets/commodities` читает из БД (markets_commodities).
- **API:** `/api/analytics/dashboard/summary` вызывает `DashboardService.get_kpi()`. `/api/markets/overview` limit до 500. Commodities: данные из БД; при ошибках GoldAPI/Alpha Vantage — кеш/последние сохранённые.
- **Rate limits:** ingestion `_fetch_with_retry` — exponential backoff при 429. Alpha Vantage TTL 4h. GoldAPI: при 403/429 — использование кеша из БД.
- **Admin Page:** секция «Состояние API» (GET `/api/admin/api-health`), кнопки «Очистить невалидные товары», «Очистить пул полностью», «Дедупликация маркетплейсов». Управление пулом: диагностика, пересчёт квот, Discovery, Scraping, clear user products. Toast cleanup-invalid показывает deleted_category_pages.
- **Products:** страница с двумя вкладками — «Все товары» (GET `/api/pool/products`) и «Мои товары» (GET `/api/products`). Компоненты: `PoolProductsTab`, `MyProductsTab`, хук `usePoolProducts`.
- **Import:** поддерживает .csv, .tsv, .xls, .xlsx, .xlsm. Preview и upload через `/api/import/products/preview` и `/api/import/products/csv`.
- **Admin pool:** GET `/api/admin/diagnostics/pool`, GET `/api/admin/diagnostics/sample-products`, GET `/api/admin/api-health`, POST `/api/admin/marketplaces/recalculate-quotas`, POST `/api/admin/marketplaces/deduplicate`, POST `/api/admin/marketplaces/set-requires-js`, POST `/api/admin/products/cleanup-invalid`, POST `/api/admin/products/clear-pool`, POST `/api/admin/products/clear-user-data`. Discovery/scrape: POST `/api/admin/discovery/trigger-all`, POST `/api/admin/pool/trigger-scrape`.
- Pipeline: marketplaces → discovery → scraping → виджеты; админ: add-by-url, discovery/trigger-all, pool/trigger-scrape, diagnostics, recalculate-quotas.
- Модули: core, marketplaces, scraper, product_pool, market_data, dashboard, user_products, analytics, alerts, digests, ai_analyst.
- Ниже — исторический снимок; ориентир — разделы про модульную архитектуру и актуальные домены.

## Обзор

Imperecta — SaaS-платформа конкурентной разведки и рыночной аналитики для e-commerce. Отслеживает цены конкурентов на любых маркетплейсах через `ScraperPool`, показывает рыночные данные (forex, крипто, сырьё, топливо, товары маркетплэйсов), генерирует ИИ-дайджесты и отправляет алерты при изменениях цен. Имеет встроенный ИИ для аналитики и обработки данных цен товаров на маркетплэйсах.  
Функционал будет расширяться до возможности совершать покупки прямо внутри приложения, добавляя в корзину товары с различных маркетплэйсов, сравнивая цены, выбирая оптимальный по цене, стоимости и скорости доставки.
Целевая аудитория: малый и средний e-commerce бизнес в Европе (Все страны) и странах СНГ (а так же все страны бывшего СССР).

---

## Маршруты (Routes)

### Backend API (REST)

Все API под префиксом `/api`, кроме `/health` и `/api/health`.

| Модуль | Метод | Путь | Описание |
|--------|-------|------|----------|
| **Health** | GET | /health | Liveness probe (Railway) |
| **Health** | GET | /api/health | DB + Redis connectivity |
| **auth** | POST | /api/auth/register | Регистрация |
| **auth** | POST | /api/auth/login | Вход |
| **auth** | POST | /api/auth/change-initial-password | Смена пароля (force) |
| **auth** | POST | /api/auth/refresh | Обновление токена |
| **auth** | POST | /api/auth/telegram-link | Привязка Telegram |
| **auth** | POST | /api/auth/telegram-disconnect | Отвязка Telegram |
| **auth** | GET | /api/auth/me | Текущий пользователь |
| **auth** | PUT | /api/auth/me | Обновление профиля |
| **telegram** | POST | /api/telegram/webhook | Webhook Telegram-бота |
| **telegram** | POST | /api/telegram/generate-link-code | Генерация кода привязки |
| **telegram** | POST | /api/telegram/unlink | Отвязка (admin) |
| **telegram** | GET | /api/telegram/status | Статус привязки |
| **pool** | GET | /api/pool/products | Товары из глобального пула (search, marketplace_id, sort, limit, offset) |
| **pool** | GET | /api/pool/categories | Маркетплейсы для фильтра |
| **pool** | GET | /api/pool/marketplace-stats | Статистика по маркетплейсам |
| **pool** | GET | /api/pool/stats | Общая статистика пула |
| **pool** | GET | /api/pool/search | Поиск по названию |
| **products** | GET | /api/products/categories | Список категорий |
| **products** | GET | /api/products | Список товаров пользователя (пагинация, search, sort) |
| **products** | GET | /api/products/at-risk | Товары в зоне риска |
| **products** | GET | /api/products/{id} | Детали товара |
| **products** | GET | /api/products/{id}/ai-recommendation | AI-рекомендация |
| **products** | POST | /api/products | Создание товара |
| **products** | PUT | /api/products/{id} | Обновление товара |
| **products** | DELETE | /api/products/{id} | Удаление товара |
| **competitors** | GET | /api/competitors | Список конкурентов |
| **competitors** | GET | /api/competitors/marketplaces | Список маркетплейсов (для селекта) |
| **competitors** | POST | /api/competitors | Создание конкурента |
| **competitors** | PUT | /api/competitors/{id} | Обновление конкурента |
| **competitors** | DELETE | /api/competitors/{id} | Удаление конкурента |
| **competitors** | POST | /api/competitors/products | Привязка товара к конкуренту |
| **competitors** | GET | /api/competitors/products/{product_id} | Товары конкурентов по product_id |
| **competitors** | GET | /api/competitors/{competitor_id}/products | Товары конкурента |
| **competitors** | DELETE | /api/competitors/products/{id} | Отвязка товара |
| **analytics** | GET | /api/analytics/products/{product_id}/price-history | История цен |
| **analytics** | GET | /api/analytics/products/{product_id}/comparison | Сравнение цен |
| **analytics** | GET | /api/analytics/products/{product_id}/forecast | Прогноз цен |
| **analytics** | GET | /api/analytics/market-forecast | Рыночный прогноз |
| **analytics** | POST | /api/analytics/simulate | Симуляция |
| **analytics** | POST | /api/analytics/advanced-simulation | Расширенная симуляция |
| **analytics** | GET | /api/analytics/competitor-benchmark | Бенчмарк конкурентов |
| **analytics** | GET | /api/analytics/comparison-matrix | Матрица сравнения |
| **analytics** | GET | /api/analytics/dashboard/summary | Сводка дашборда |
| **analytics** | GET | /api/analytics/dashboard/anomalies | Аномалии |
| **dashboard** | GET | /api/dashboard/kpi | KPI-метрики |
| **dashboard** | GET | /api/dashboard/anomalies | Аномалии дашборда |
| **dashboard** | GET | /api/dashboard/aggregate-trend | Агрегированный тренд |
| **alerts** | GET | /api/alerts | Список алертов |
| **alerts** | POST | /api/alerts | Создание алерта |
| **alerts** | PUT | /api/alerts/{id} | Обновление алерта |
| **alerts** | DELETE | /api/alerts/{id} | Удаление алерта |
| **alerts** | GET | /api/alerts/events | События алертов |
| **alerts** | GET | /api/alerts/events/{event_id}/explanation | AI-объяснение события |
| **alerts** | POST | /api/alerts/events/{event_id}/auto-response | AI-автоответ |
| **digests** | GET | /api/digests | Список дайджестов |
| **digests** | GET | /api/digests/{id} | Детали дайджеста |
| **import** | POST | /api/import/auto-categorize | Авто-категоризация |
| **import** | POST | /api/import/products/preview | Превью импорта (CSV, TSV, Excel) |
| **import** | POST | /api/import/products/csv | Импорт CSV/TSV/Excel |
| **import** | GET | /api/import/products/template | Шаблон CSV |
| **ai** | POST | /api/ai/chat | Отправка сообщения в AI-чат |
| **ai** | GET | /api/ai/sessions | Список сессий AI-чата |
| **ai** | GET | /api/ai/sessions/{session_id} | Детали сессии |
| **ai** | DELETE | /api/ai/sessions/{session_id} | Удаление сессии |
| **markets** | GET | /api/markets/preferences | Настройки рынков |
| **markets** | PUT | /api/markets/preferences | Обновление настроек |
| **markets** | GET | /api/markets/refresh-metadata | Метаданные обновления |
| **markets** | GET | /api/markets/forex | Forex (виджет) |
| **markets** | GET | /api/markets/crypto | Крипто (виджет) |
| **markets** | GET | /api/markets/commodities | Сырьё (виджет) |
| **markets** | GET | /api/markets/ticker?country=UA | Бегущая строка (forex+crypto+commodities+fuel по стране) |
| **markets** | GET | /api/markets/fuel?country=UA | Цены на топливо (бензин, дизель, LPG) |
| **markets** | GET | /api/markets/overview?sort=&limit= | Market Overview (реальные данные из price_snapshots) |
| **markets** | GET | /api/markets/category-analytics | Аналитика по категориям |
| **markets** | GET | /api/markets/marketplace-analytics | Аналитика по маркетплейсам |
| **markets** | GET | /api/markets/opportunities | Блоки возможностей |
| **markets** | POST | /api/markets/ingest | Запуск инжеста (superuser) |
| **admin** | GET | /api/admin/stats | Статистика админки |
| **admin** | GET | /api/admin/users | Список пользователей |
| **admin** | GET | /api/admin/claude-status | Статус Claude API |
| **admin** | GET | /api/admin/api-health | Статус внешних API (forex, crypto, commodities, decodo, claude и др.) |
| **admin** | GET | /api/admin/diagnostics/pool | Диагностика пула (marketplaces, products, discovery_logs) |
| **admin** | GET | /api/admin/diagnostics/sample-products | 10 сэмплов global_products для отладки |
| **admin** | POST | /api/admin/products/cleanup-invalid | Удаление global_products (длинные URL, невалидные, страницы категорий) |
| **admin** | POST | /api/admin/products/clear-pool | Полная очистка пула (global_products + snapshots) |
| **admin** | POST | /api/admin/products/clear-user-data | Удаление всех пользовательских товаров |
| **admin** | DELETE | /api/admin/products/clear-test-data | Удаление тестовых товаров |
| **admin** | GET | /api/admin/marketplaces | Список маркетплейсов |
| **admin** | GET | /api/admin/marketplaces/{marketplace_id}/logs | Логи маркетплейса |
| **admin** | POST | /api/admin/marketplaces | Добавление маркетплейса |
| **admin** | POST | /api/admin/marketplaces/deduplicate | Дедупликация маркетплейсов (rozetka.ua ↔ rozetka.com.ua) |
| **admin** | POST | /api/admin/marketplaces/recalculate-quotas | Пересчёт квот пула |
| **admin** | POST | /api/admin/marketplaces/set-requires-js | Установка requires_js для маркетплейсов |
| **admin** | DELETE | /api/admin/marketplaces/{marketplace_id} | Удаление маркетплейса |
| **admin** | POST | /api/admin/discovery/trigger/{marketplace_id} | Запуск discovery для одного маркетплейса |
| **admin** | POST | /api/admin/discovery/trigger-all | Запуск discovery для всех |
| **admin** | POST | /api/admin/pool/trigger-scrape | Запуск scraping пула товаров |
| **admin** | POST | /api/admin/trigger-scrape | Ручной запуск парсинга competitor_products |
| **admin** | GET | /api/admin/scrape-activity | Активность парсинга |
| **admin** | GET | /api/admin/error-distribution | Распределение ошибок |

### Frontend (React Router)

| Путь | Компонент | Описание |
|------|-----------|----------|
| /ai.market.intelligence.agent | LandingPage | Публичный лендинг (редирект на / при авторизации) |
| /login | LoginPage | Вход (PublicAuthRoute) |
| /register | RegisterPage | Регистрация (PublicAuthRoute) |
| /forgot-password | ForgotPasswordPage | Восстановление пароля (PublicAuthRoute) |
| /change-password | ChangePasswordRoute | Смена пароля (force_password_change) |
| / | DashboardLayout | Корневой layout (ProtectedRoute) |
| /dashboard | DashboardPage | Рынки: TickerBar, Widgets, MarketDataTable, Analytics |
| /products | ProductsPage | Две вкладки: «Все товары» (пул), «Мои товары» (CRUD) |
| /products/:id | ProductDetailPage | Детали товара, график цен, конкуренты |
| /competitors | CompetitorsPage | CRUD конкурентов |
| /alerts | AlertsPage | CRUD алертов, события |
| /digests | DigestsPage | Список дайджестов |
| /import | ImportPage | Импорт CSV/TSV/Excel (.csv, .tsv, .xls, .xlsx, .xlsm) |
| /analytics | AnalyticsPage | Аналитика, тренды, прогнозы |
| /ai | AIAnalystRoute | AI-чат (locked для Trial/Free) |
| /settings | SettingsPage | Профиль, Telegram, план |
| /admin | AdminPage | Админ-панель (SuperuserRoute): stats, marketplaces, pool management, scrape activity |
| * | NotFoundPage | 404 |

---

## Технический стек

### Backend
- **Python 3.12** + **FastAPI** — REST API
- **SQLAlchemy 2.0 (async)** + **asyncpg** — ORM и подключение к PostgreSQL
- **SQLAlchemy (sync)** + **psycopg2** — sync_session_factory для Celery workers; ingest_market_data создаёт локальный async engine/session (не использует глобальный), чтобы избежать ошибки «different event loop» при повторном запуске
- **Alembic** — миграции БД (head: `004_fix_real_state`; таблица версий в схеме `alembic_meta`)
- **Celery** + **Redis** — фоновые задачи (парсинг, алерты, дайджесты)
- **Decodo Web Scraping API** — основной метод парсинга (managed, anti-bot; DECODO_USERNAME, DECODO_PASSWORD, DECODO_ENABLED)
- **Playwright** — fallback для JS-rendered страниц при отключённом или недоступном Decodo
- **BeautifulSoup + httpx** — извлечение цен из HTML (JSON-LD, meta, DOM)
- **Anthropic Claude API** — генерация ИИ-дайджестов, AI-чат, авто-категоризация товаров
- **Resend** — отправка email-уведомлений
- **python-telegram-bot** — Telegram-бот для алертов
- **JWT (python-jose)** — аутентификация (access 30 мин, refresh 7/30 дней при «Запомнить меня»)

### Frontend
- **Vite 6** + **React 19** + **TypeScript**
- **React Router 7** — маршрутизация (SPA)
- **Tailwind CSS 4** + **shadcn/ui** (Radix UI) — UI-компоненты
- **Recharts** — графики цен (PriceChart, ComparisonChart, TrendBadge)
- **TanStack Query v5** — серверное состояние и кеширование
- **Zustand v5** — клиентское состояние (auth, persist: localStorage / sessionStorage)
- **framer-motion** — анимации и переходы
- **Axios** — HTTP-клиент
- **react-i18next** — локализация (en, ru, ar, zh, es, fr, uk, ro в public/locales)
- **react-markdown** — рендер markdown в AI-чате
- **DOMPurify** — санитизация HTML перед dangerouslySetInnerHTML (DigestsPage)
- **Vitest** — unit-тесты frontend (sanitize, security)
- **Sonner** — toast-уведомления
- **next-themes** — переключение темы (light/dark, по умолчанию dark)

### Безопасность
- **Snyk** — сканирование зависимостей и кода
- **Bandit** — статический анализ Python-кода
- **pip-audit** + **Safety** — проверка уязвимостей в Python-пакетах
- **Gitleaks** — поиск утёкших секретов в git-истории
- **eslint-plugin-security** — безопасность frontend-кода
- **DOMPurify** — санитизация HTML в DigestsPage (XSS-защита)
- **TELEGRAM_WEBHOOK_SECRET** — проверка webhook Telegram (constant-time, обязательна при включённом боте)

---

## Облачная инфраструктура

### Схема связей

```
┌──────────────────────────────────────────────────────────────────┐
│                        ПОЛЬЗОВАТЕЛЬ                              │
│                     (браузер / Telegram)                          │
└──────────┬───────────────────────────────────┬──────────────────┘
           │ HTTPS                              │ Telegram API
           ▼                                    ▼
┌─────────────────────┐              ┌─────────────────────┐
│  CLOUDFLARE PAGES   │              │   TELEGRAM BOT API  │
│  React SPA (Vite)   │              │   (api.telegram.org) │
│  imperecta.pages.dev│              └──────────┬──────────┘
└──────────┬──────────┘                         │
           │ HTTPS (VITE_API_URL)               │ webhook
           ▼                                    ▼
┌──────────────────────────────────────────────────────────────────┐
│                     RAILWAY (3 сервиса)                           │
│  imperecta (backend), celery-worker, celery-beat                  │
└───────┬──────────────┬──────────────┬───────────────┬────────────┘
        ▼              ▼              ▼               ▼
┌──────────────┐ ┌───────────┐ ┌───────────┐ ┌──────────────┐
│   SUPABASE   │ │  UPSTASH   │ │ ANTHROPIC │ │    RESEND    │
│  PostgreSQL  │ │   Redis   │ │ Claude API│ │  Email API   │
└──────────────┘ └───────────┘ └───────────┘ └──────────────┘
```

---

## Структура проекта (все файлы, кроме /dist и /node_modules)

Узел `backend/app` упрощён: детали модулей — в разделе «Backend: краткое описание файлов кода».

```
imperecta/
├── backend/
│   ├── alembic/
│   │   ├── env.py                    # Alembic async; version_table_schema=alembic_meta
│   │   └── versions/
│   │       ├── 001_v2_schema.py      # Full v2 rebuild: dims, facts, seeds, MVs, fact_price partitions
│   │       ├── 002_v2_additions.py   # Crypto/commodity/fuel facts, discovery cols, url_hash, preferences, fixes
│   │       ├── 003_fix_users_columns.py # Additive users columns + pg_trgm ensure
│   │       ├── 004_fix_real_state.py # Production drift fix: users type/columns + legacy cleanup
│   │       └── .gitkeep
│   ├── alembic.ini                   # Alembic config
│   ├── app/
│   │   ├── common/                   # deps.py, exceptions.py
│   │   ├── modules/                  # Доменная логика и API (см. «Backend: краткое описание»)
│   │   │   ├── core/                 # auth, admin, telegram
│   │   │   ├── marketplaces/
│   │   │   ├── scraper/              # discovery, scraper_pool, extractors, service, tasks, api (engine удалён)
│   │   │   ├── product_pool/
│   │   │   ├── market_data/
│   │   │   ├── dashboard/
│   │   │   ├── user_products/
│   │   │   ├── analytics/
│   │   │   ├── alerts/
│   │   │   ├── digests/
│   │   │   └── ai_analyst/
│   │   ├── models/                   # ORM v2 (единый слой для Alembic)
│   │   │   ├── __init__.py
│   │   │   ├── core.py               # users, user_subscriptions, user_products
│   │   │   ├── dimensions.py         # dim_*
│   │   │   ├── facts.py              # fact_*
│   │   │   └── app_tables.py         # alerts, digests, ai_chat, scrape_*, api_logs, data_exports
│   │   ├── entitlements/
│   │   │   ├── __init__.py
│   │   │   └── plan.py
│   │   ├── schemas/                  # минимальный пакет (legacy)
│   │   │   └── __init__.py
│   │   ├── workers/
│   │   │   ├── celery_app.py         # include: modules tasks + cleanup_tasks + maintenance_tasks
│   │   │   ├── scheduler.py          # Beat schedule (incl. MV refresh, fact_price partitions)
│   │   │   ├── cleanup_tasks.py
│   │   │   ├── maintenance_tasks.py  # refresh_materialized_views, ensure_fact_price_partitions
│   │   │   └── __init__.py
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── database.py
│   │   └── main.py                   # FastAPI, роутеры из modules/* → /api
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── security.cfg                  # Bandit config
│   ├── .snyk
│   └── tests/
│       ├── conftest.py
│       ├── test_admin_contract.py
│       ├── test_ai_contract.py
│       ├── test_analytics_contract.py
│       ├── test_auth_contract.py
│       ├── test_dashboard_contract.py
│       ├── test_health.py
│       ├── test_markets_contract.py
│       ├── test_products_contract.py
│       ├── test_security.py
│       └── test_telegram_webhook.py
├── docker-compose.yml
├── docker-compose.prod.yml
├── e2e/
│   ├── .env.example
│   ├── package.json
│   ├── package-lock.json
│   ├── playwright.config.ts
│   └── tests/
│       ├── auth.spec.ts
│       ├── dashboard.spec.ts
│       ├── products.spec.ts
│       ├── security.spec.ts
│       └── smoke.spec.ts
├── frontend/
│   ├── components.json               # shadcn config
│   ├── Dockerfile
│   ├── Dockerfile.prod
│   ├── eslint.config.js
│   ├── functions/
│   │   └── _middleware.js             # Cloudflare edge: auth routing
│   ├── index.html
│   ├── nginx.conf
│   ├── package.json
│   ├── package-lock.json
│   ├── public/
│   │   ├── android-chrome-192x192.png
│   │   ├── android-chrome-512x512.png
│   │   ├── apple-touch-icon.png
│   │   ├── favicon-16x16.png
│   │   ├── favicon-32x32.png
│   │   ├── favicon.ico
│   │   ├── images/
│   │   │   ├── Contact.png
│   │   │   ├── FAQs.png
│   │   │   ├── Home.png
│   │   │   ├── logo_dark.png
│   │   │   ├── logo_light.png
│   │   │   └── Services.png
│   │   ├── locales/
│   │   │   ├── ar/translation.json
│   │   │   ├── en/translation.json
│   │   │   ├── es/translation.json
│   │   │   ├── fr/translation.json
│   │   │   ├── ro/translation.json
│   │   │   ├── ru/translation.json
│   │   │   ├── uk/translation.json
│   │   │   └── zh/translation.json
│   │   ├── _routes.json
│   │   └── site.webmanifest
│   ├── src/
│   │   ├── api/
│   │   │   ├── admin.ts
│   │   │   ├── ai.ts
│   │   │   ├── alerts.ts
│   │   │   ├── analytics.ts
│   │   │   ├── auth.ts
│   │   │   ├── client.ts             # Axios instance, interceptors
│   │   │   ├── competitors.ts
│   │   │   ├── digests.ts
│   │   │   ├── import.ts
│   │   │   ├── markets.ts
│   │   │   ├── products.ts
│   │   │   └── setupAuth.ts          # Auth interceptors setup
│   │   ├── App.tsx                   # Routes, QueryClient, ThemeProvider
│   │   ├── AppWithInit.tsx           # App + i18n init
│   │   ├── components/
│   │   │   ├── ai/
│   │   │   │   ├── ChatInput.tsx
│   │   │   │   ├── ChatMessage.tsx
│   │   │   │   ├── PresetQuestions.tsx
│   │   │   │   └── TypingIndicator.tsx
│   │   │   ├── AIAnalystRoute.tsx    # Route guard, locked state
│   │   │   ├── analytics/
│   │   │   │   ├── MarketComparisonSection.tsx
│   │   │   │   └── TrendsChart.tsx
│   │   │   ├── auth/
│   │   │   │   ├── authContext.ts
│   │   │   │   ├── AuthLayout.tsx
│   │   │   │   └── AuthProvider.tsx
│   │   │   ├── ChangePasswordRoute.tsx
│   │   │   ├── dashboard/
│   │   │   │   ├── CountrySelector.tsx
│   │   │   │   ├── MarketDataTable.tsx      # Market Overview (API only, empty state + Go to Products)
│   │   │   │   ├── MarketsAnalyticsSection.tsx
│   │   │   │   ├── MarketsTickerBar.tsx     # Бегущая строка
│   │   │   │   └── MarketsWidgetsSection.tsx # 4 виджета: Forex, Crypto, Commodities, Fuel
│   │   │   ├── layout/
│   │   │   │   ├── BottomNavigation.tsx
│   │   │   │   ├── DashboardLayout.tsx
│   │   │   │   ├── Header.tsx
│   │   │   │   ├── MobileSidebar.tsx
│   │   │   │   └── Sidebar.tsx
│   │   │   ├── competitors/
│   │   │   │   ├── ComparisonMatrix.tsx
│   │   │   │   └── PriceSparkline.tsx
│   │   │   ├── products/
│   │   │   │   ├── PoolProductsTab.tsx   # Вкладка «Все товары» (пул)
│   │   │   │   └── MyProductsTab.tsx     # Вкладка «Мои товары» (CRUD)
│   │   │   ├── LoadingScreen.tsx
│   │   │   ├── ProtectedRoute.tsx
│   │   │   ├── PublicAuthRoute.tsx
│   │   │   ├── SessionExpiryWarning.tsx
│   │   │   ├── SuperuserRoute.tsx
│   │   │   ├── ui/                     # shadcn components
│   │   │   │   ├── avatar.tsx
│   │   │   │   ├── badge.tsx
│   │   │   │   ├── badge-variants.ts
│   │   │   │   ├── button.tsx
│   │   │   │   ├── button-variants.ts
│   │   │   │   ├── card.tsx
│   │   │   │   ├── checkbox.tsx
│   │   │   │   ├── collapsible.tsx
│   │   │   │   ├── dialog.tsx
│   │   │   │   ├── dropdown-menu.tsx
│   │   │   │   ├── .gitkeep
│   │   │   │   ├── input.tsx
│   │   │   │   ├── LanguageSelector.tsx
│   │   │   │   ├── progress.tsx
│   │   │   │   ├── radio-group.tsx
│   │   │   │   ├── select.tsx
│   │   │   │   ├── separator.tsx
│   │   │   │   ├── sheet.tsx
│   │   │   │   ├── skeleton.tsx
│   │   │   │   ├── slider.tsx
│   │   │   │   ├── switch.tsx
│   │   │   │   ├── table.tsx
│   │   │   │   ├── tabs.tsx
│   │   │   │   └── tooltip.tsx
│   │   │   └── ui-custom/
│   │   │       ├── CircularScore.tsx
│   │   │       ├── EmptyState.tsx
│   │   │       ├── MarketplaceBadge.tsx
│   │   │       ├── PageHeader.tsx
│   │   │       ├── PlanLimitBanner.tsx
│   │   │       ├── PriceChangeCell.tsx
│   │   │       ├── PromoBadge.tsx
│   │   │       ├── SearchableMarketplaceSelect.tsx
│   │   │       ├── StatCard.tsx
│   │   │       └── TrendBadge.tsx
│   │   ├── data/
│   │   │   └── filters.ts
│   │   ├── hooks/
│   │   │   ├── useAdmin.ts
│   │   │   ├── useAlerts.ts
│   │   │   ├── useAnalytics.ts
│   │   │   ├── useAuth.ts
│   │   │   ├── useCompetitors.ts
│   │   │   ├── useDebounce.ts
│   │   │   ├── useEntitlements.ts
│   │   │   ├── usePlanLimits.ts
│   │   │   ├── usePoolProducts.ts   # Пул товаров (GET /api/pool/products)
│   │   │   ├── useProducts.ts
│   │   │   └── useSidebar.ts
│   │   ├── i18n/
│   │   │   └── index.ts
│   │   ├── index.css
│   │   ├── lib/
│   │   │   ├── authCookie.ts          # Cookie for edge middleware
│   │   │   ├── authStorage.ts
│   │   │   ├── countries.ts
│   │   │   ├── countryNames.ts
│   │   │   ├── countryResolution.ts
│   │   │   ├── countrySearch.ts
│   │   │   ├── countrySearch.test.ts
│   │   │   ├── design-tokens.ts
│   │   │   ├── formatters.ts
│   │   │   ├── routes.ts              # PUBLIC_ROUTES, getLoginUrl, getReturnPath
│   │   │   ├── safeNumber.ts         # safeFixed, safeNumber — null-safe formatting
│   │   │   ├── sanitize.ts
│   │   │   ├── sanitize.test.ts
│   │   │   ├── tickerBarData.ts       # buildTickerBarItems (forex+crypto+commodities)
│   │   │   ├── tickerBarData.test.ts
│   │   │   └── utils.ts
│   │   ├── main.tsx
│   │   ├── pages/
│   │   │   ├── AdminPage.tsx
│   │   │   ├── AIAnalystPage.tsx
│   │   │   ├── AiPage.tsx
│   │   │   ├── AlertsPage.tsx
│   │   │   ├── AnalyticsPage.tsx
│   │   │   ├── auth/
│   │   │   │   ├── ForgotPasswordPage.tsx
│   │   │   │   ├── LoginPage.tsx
│   │   │   │   └── RegisterPage.tsx
│   │   │   ├── CompetitorsPage.tsx
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── DigestsPage.tsx
│   │   │   ├── ForcePasswordChangePage.tsx
│   │   │   ├── ImportPage.tsx
│   │   │   ├── landing/
│   │   │   │   └── LandingPage.tsx
│   │   │   ├── NotFoundPage.tsx
│   │   │   ├── ProductDetailPage.tsx
│   │   │   ├── ProductsPage.tsx
│   │   │   └── SettingsPage.tsx
│   │   ├── stores/
│   │   │   └── authStore.ts           # Zustand auth store
│   │   ├── styles/
│   │   │   ├── components.css
│   │   │   └── glass.css
│   │   ├── types/
│   │   │   └── filters.ts
│   │   └── vite-env.d.ts
│   ├── tsconfig.json
│   ├── tsconfig.tsbuildinfo
│   └── vite.config.ts
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── test.yml
├── .gitignore
├── .gitleaks.toml
├── Imperecta_Cursor_Project_Description.md
├── Imperecta_Database_Schema_v2.md   # Спецификация БД v2 (star schema, MVs, seeds)
├── scripts/
│   ├── install-hooks.sh
│   └── prepare-commit-msg
└── .snyk
```

---

## Backend: краткое описание файлов кода

### backend/app (модульная архитектура)

- `main.py` — инициализация FastAPI-приложения, middleware, CORS, health-check и подключение роутеров ТОЛЬКО из `modules/*`.
- `config.py` — централизованные настройки приложения через переменные окружения.
- `database.py` — async/sync подключения к PostgreSQL, фабрики сессий для API и workers.
- `common/deps.py` — общие зависимости FastAPI (DB session, текущий пользователь, superuser-проверки).
- `modules/` — доменные bounded-context модули.

### backend/app/modules (актуальные домены)

- `core/` — auth, users, plans, admin bootstrap (`api_auth.py`, `api_telegram.py`, `auth/service.py`, `models.py`, `schemas.py`).
- `marketplaces/` — управление пулом маркетплейсов и admin endpoints (`models.py`, `service.py`, `api.py`).
- `scraper/` — модуль парсинга и discovery (`scraper_pool.py`, `extractors.py`, `discovery.py`, `service.py`, `tasks.py`, `api.py`, `proxy_manager.py`).
- `product_pool/` — глобальный пул товаров (`models.py`, `schemas.py`, `service.py`, `api.py`).
- `market_data/` — forex/crypto/commodities/fuel/ticker + ingest/aggregate/providers (`models.py`, `schemas.py`, `service.py`, `ingestion.py`, `aggregation.py`, `providers/*`, `tasks.py`, `api.py`).
- `dashboard/` — KPI, overview, category/marketplace analytics, opportunities (`service.py`, `schemas.py`, `api.py`).
- `user_products/` — пользовательские товары/конкуренты/импорт (`models.py`, `schemas.py`, `service.py`, `api_products.py`, `api_competitors.py`, `api_import.py`).
- `analytics/` — прогнозы, benchmark, comparison APIs (`service.py`, `schemas.py`, `api.py`).
- `alerts/` — правила алертов, события, уведомления, background tasks (`models.py`, `schemas.py`, `service.py`, `notifications.py`, `tasks.py`, `api.py`).
- `digests/` — генерация и выдача дайджестов (`models.py`, `schemas.py`, `service.py`, `tasks.py`, `api.py`).
- `ai_analyst/` — AI чат, рекомендации, Claude client/monitoring (`models.py`, `schemas.py`, `service.py`, `claude_client.py`, `monitor.py`, `api.py`).

### API routes (backend/app/modules/*)

- `/api/auth/*` — `modules/core/api_auth.py`
- `/api/telegram/*` — `modules/core/api_telegram.py`
- `/api/admin/marketplaces/*` — `modules/marketplaces/api.py`
- `/api/admin/discovery/*`, `/api/admin/pool/*`, `/api/admin/scrape-*` — `modules/scraper/api.py`
- `/api/pool/*` — `modules/product_pool/api.py`
- `/api/markets/*` (data + dashboard views) — `modules/market_data/api.py` + `modules/dashboard/api.py`
- `/api/products/*`, `/api/competitors/*`, `/api/import/*` — `modules/user_products/*`
- `/api/analytics/*` — `modules/analytics/api.py`
- `/api/alerts/*` — `modules/alerts/api.py`
- `/api/digests/*` — `modules/digests/api.py`
- `/api/ai/*` — `modules/ai_analyst/api.py`

### Удалённые legacy-каталоги

- Старые плоские каталоги `backend/app/api/*`, `backend/app/services/*`, `backend/app/schemas/*`, `backend/app/scrapers/*`, `backend/app/notifications/*` удалены как источник runtime-кода.
- `backend/app/models/__init__.py` оставлен как единая точка реэкспорта ORM-моделей для Alembic metadata discovery.

### backend/app/workers (Celery tasks)

- `__init__.py` — пакетный инициализатор worker-модуля.
- `celery_app.py` — создание и конфигурация Celery-приложения: `include` — `app.modules.*.tasks`, `app.workers.cleanup_tasks`, `app.workers.maintenance_tasks`.
- `scheduler.py` — подключение beat: фактически `celery_app.conf.beat_schedule = {}` (периодические задачи отключены до явного включения). В коде задач по-прежнему доступны **refresh_materialized_views** и **ensure_fact_price_partitions** (maintenance_tasks).
- `cleanup_tasks.py` — очистка устаревших технических и ценовых данных (`cleanup_old_data`).
- `maintenance_tasks.py` — `refresh_materialized_views` (REFRESH MATERIALIZED VIEW CONCURRENTLY для MV из 001), `ensure_fact_price_partitions` (CREATE TABLE IF NOT EXISTS … PARTITION OF `fact_price`).

### backend/alembic и backend/alembic/versions

- `alembic/env.py` — async-миграции; `version_table_schema='alembic_meta'` (версия не теряется при `DROP SCHEMA public CASCADE` в `001_v2_schema`).
- `versions/001_v2_schema.py` — star schema v2, extensions, партиции `fact_price` (202601–202612), seeds, MV, восстановление `users`. `downgrade` — `NotImplementedError`.
- `versions/002_v2_additions.py` — инкрементальные ALTER/CREATE: три fact-таблицы рынков, поля discovery в `dim_marketplace`, `url_hash`, `users.preferences`, фикс `week_iso`, `DROP EXTENSION IF EXISTS jsonb_plperl`. `downgrade` — откат ADD/DROP.
- `versions/003_fix_users_columns.py` — additive migration: гарантирует наличие v2-колонок в `users` и `pg_trgm` (`IF NOT EXISTS`).
- `versions/004_fix_real_state.py` — migration for real production drift: конверсия `users.plan` enum->varchar, cleanup legacy tables/types/sequences, доинициализация app-таблиц v2, повторный `pg_trgm`.
- Старая цепочка миграций 001–016 из репозитория удалена; при необходимости история — только в git.

### backend/tests (контрактные и security тесты)

- `__init__.py` — пакетный инициализатор тестов.
- `conftest.py` — общие фикстуры, подготовка test client и зависимостей.
- `test_health.py` — проверки `/health` и `/api/health`.
- `test_auth_contract.py` — контракт auth endpoint-ов.
- `test_products_contract.py` — контракт API товаров.
- `test_analytics_contract.py` — контракт аналитических endpoint-ов.
- `test_dashboard_contract.py` — контракт dashboard endpoint-ов.
- `test_markets_contract.py` — контракт рынков и market widgets endpoint-ов.
- `test_ai_contract.py` — контракт AI-chat endpoint-ов.
- `test_admin_contract.py` — контракт административного API.
- `test_telegram_webhook.py` — валидация webhook Telegram и секретов.
- `test_security.py` — security-проверки backend-кода и конфигурации.

### backend (инфраструктурные файлы)

- `Dockerfile` — сборка backend-контейнера.
- `.dockerignore` — исключения для docker build-контекста.
- `requirements.txt` — зависимости Python-окружения.
- `pyproject.toml` — конфигурация инструментов и Python-проекта.
- `alembic.ini` — настройки Alembic.
- `security.cfg` — профиль/настройки security-сканирования.
- `.snyk` — правила и политика Snyk для backend-зависимостей.

---

## Исторический снимок: обновления архитектуры (PR-6)

Ниже — этап с плоскими каталогами `app/api`, `app/services` и отдельными моделями пула; **текущее состояние** — модульная структура `app/modules/*` и **БД v2** (`dim_*` / `fact_*`, см. актуализацию и `Imperecta_Database_Schema_v2.md`). Пул и discovery живут в `modules/scraper`, `modules/product_pool`, `modules/marketplaces`; глобальные таблицы v1 заменены целевой схемой v2.

### Новые backend-модули (исторически)

- `backend/app/models/global_product.py` — глобальный пул товаров и история цен (`global_products`, `global_price_snapshots`).
- `backend/app/models/discovery_log.py` — журнал сессий discovery crawler (`discovery_logs`).
- `backend/app/scrapers/extractors.py` — уровни извлечения данных (JSON-LD, meta, custom selectors, auto-detect).
- `backend/app/scrapers/scraper_pool.py` — failover-скрейпинг (Decodo -> httpx -> Playwright) и completeness-check.
- `backend/app/scrapers/discovery_crawler.py` — discovery pipeline для обхода маркетплейсов и сбора URL товаров.
- `backend/app/services/marketplace_pool_service.py` — управление пулом маркетплейсов (add-by-url, import txt/csv, quota recalc).
- `backend/app/services/global_scrape_service.py` — скрейпинг и аналитика глобального пула товаров.
- `backend/app/services/product_pool_service.py` — read-only доступ к пулу товаров для `/api/markets/overview` и `/api/pool/*`.
- `backend/app/workers/discovery_tasks.py` — celery-задачи discovery/scraping для global pool.
- `backend/app/api/product_pool.py` — API `/api/pool/*`.
- `backend/app/schemas/global_product.py` — схемы ответов для глобального пула товаров.

### Удалено / вычищено (исторически)

- `backend/app/services/seed_service.py` — удалён.
- `backend/app/models/markets_overview.py` — удалён (overview читает из `global_products`).
- Удалены мёртвые методы/импорты в `markets_service.py` и legacy overview materialization через `markets_overview`.

### Новые API routes (pool + admin)

- `/api/pool/products`, `/api/pool/categories`, `/api/pool/marketplace-stats`, `/api/pool/stats`, `/api/pool/search`
- `/api/admin/diagnostics/pool`, `/api/admin/products/clear-user-data`
- `/api/admin/marketplaces/recalculate-quotas`, `/api/admin/marketplaces/set-requires-js`
- `/api/admin/marketplaces/add-by-url`, `/api/admin/marketplaces/import-file`
- `/api/admin/discovery/trigger/{marketplace_id}`, `/api/admin/discovery/trigger-all`
- `/api/admin/pool/trigger-scrape`

### Двухуровневый pipeline

- **Discovery:** `DiscoveryCrawler` собирает URL товаров в `global_products` с учётом квот и rate-limit.
- **Scraping:** `GlobalScrapeService` обновляет цены/метрики, пишет snapshot-историю и агрегаты изменений.

---

## Функционал

### Dashboard (страница Рынки)

- **MarketsTickerBar** — бегущая строка: GET /api/markets/ticker?country=, marquee-анимация, пауза при hover
- **MarketsWidgetsSection** — 4 виджета: Forex, Crypto, Commodities, Fuel
  - Forex/Crypto/Commodities: избранное (звёздочка), API: forex, crypto, commodities; error/cached в ответе при сбое API
  - Fuel: GET /api/markets/fuel?country=, gasoline_95, diesel, lpg
- **MarketDataTable** — Market Overview: данные из global pool (`/api/markets/overview`), поиск, фильтр по маркетплейсу, pagination, кликабельный URL товара, image fallback, TREND badge
- **MarketsAnalyticsSection** — данные из `/api/pool/marketplace-stats` и `/api/pool/stats`, empty state при пустом пуле
- **CountrySelector** — выбор страны (preferred_country_code), поиск, мета-опции Europe/CIS, при Save — invalidate ticker/fuel/forex

### Entitlements (планы и лимиты)

| ServiceTier | UserPlan | Products | Competitors | AI Analyst |
|-------------|----------|----------|-------------|------------|
| Trial | trial | 999 | 999 | нет |
| Free | starter | 50 | 15 | нет |
| Paid Full | business, pro | 999 | 999 | да |

### Celery задачи

**Примечание:** при пустом `beat_schedule` автоматический триггер по расписанию отключён; таблица описывает назначение задач и типичные интервалы после включения beat.

| Задача | Триггер (при включённом beat) | Описание |
|--------|------------------------------|----------|
| scrape_single | API / scrape_all | Парсинг одного competitor_product: fetch → extract → snapshots → ScrapeLog |
| scrape_user_products | API | Парсинг всех товаров пользователя (stagger) |
| scrape_all | Beat каждые 6 ч | Очередь scrape_single для активных competitor_products |
| ingest_market_data | Beat каждые 2 ч | Forex, crypto, fuel (без commodities); отдельный engine/session per run |
| ingest_commodities | Beat 0,6,12,18 UTC | Commodities (XAU, XAG, XPT, XPD, WTI, BRENT) |
| discover_all_marketplaces | Beat ежедневно 03:00 | Discovery по активным маркетплейсам (v2 pool) |
| scrape_all_pool_products | Beat каждые 6 ч | Скрейпинг stale из пула (fact_listing / dim_product) |
| check_pool_completeness | Beat каждые 3 ч (:30) | Переочередь incomplete в пуле |
| cleanup_old_data | Beat вс 04:00 | Retention scrape_logs, api_logs и др. |
| check_alerts | после scrape_single | Сравнение цен, email/Telegram |
| schedule_weekly_digests | Beat пт 18:00 | Еженедельные дайджесты |
| schedule_daily_digests | Beat ежедневно 08:00 | Ежедневные дайджесты (pro) |
| refresh_materialized_views | Beat каждый час :15 | REFRESH MV CONCURRENTLY `mv_daily_price_summary`, `mv_marketplace_health` |
| ensure_fact_price_partitions | Beat 1-е число 02:00 UTC | Партиции `fact_price` на +3 месяца |

---

## Текущий статус

- [x] Backend: FastAPI, Celery, scraper stack (extractors + scraper_pool + discovery_crawler), global product pool и discovery pipeline
- [x] Frontend: Landing, 15+ страниц, entitlements, AIAnalystRoute (locked), PlanLimitBanner
- [x] Auth: JWT, «Запомнить меня», telegram-link/disconnect в auth
- [x] Entitlements: Trial/Free/Paid Full, AI Analyst только для Paid
- [x] Миграции Alembic v2: `001_v2_schema` + `002_v2_additions` + `003_fix_users_columns` + `004_fix_real_state` (включая repair-слой для mixed legacy/v2 состояния; `alembic_meta`)
- [x] Локальная разработка: docker-compose
- [x] CI: ruff, pytest, eslint, vitest, build, security
- [x] Markets: overview переключён на global pool (`/api/markets/overview`), API `/api/pool/*`, discovery/scraping celery tasks, обновлённый beat schedule
- [x] Security: Telegram webhook secret, DOMPurify (DigestsPage), security tests
- [ ] Успешный деплой backend (Railway)
- [ ] Успешный деплой frontend (Cloudflare)
- [ ] E2E проверка (регистрация → товар → парсинг)
- [ ] Closed beta

---

## Правила для Cursor

- Все комментарии в коде и имена переменных, функций, классов — **только на английском**
- UI тексты — на русском языке
- Не делать ничего сверх того, что запрошено
- При изменении backend — не трогать frontend и наоборот
- При изменении конфигурации — не трогать бизнес-логику
- **Git:** не использовать `--trailer "Made-with: Cursor"` и подобные трейлеры атрибуции ИИ в коммитах
