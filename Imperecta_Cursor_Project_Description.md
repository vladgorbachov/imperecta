# Imperecta — Описание проекта для Cursor IDE

## Актуализация (после PR-7 и PR-1–PR-5)

- Backend в модульной архитектуре `backend/app/modules/*`. Роутеры из `modules/*` под префиксом `/api` в `main.py`.
- **Alembic:** 015 = `015_global_products`, 016 = `016_drop_digest_summary_json`.
- **Digests:** `generate_digest` из `app.modules.ai_analyst.claude_client`.
- **Celery:** `celery_app.conf.include` (scraper, alerts, digests, market_data); `cleanup_old_data` в `app.workers.cleanup_tasks`. Beat: scrape_all, discover_all_marketplaces, scrape_all_pool_products, check_pool_completeness, ingest_market_data, digests, cleanup.
- **Decodo:** в `scraper/engine.py` и `scraper/scraper_pool.py` слой Decodo вызывается только при `decodo_enabled` и непустых `decodo_username` и `decodo_password`; при пустых credentials — skip и fallback на httpx/Playwright.
- **API:** `/api/analytics/dashboard/summary` вызывает `DashboardService.get_kpi()`. `/api/markets/overview` limit до 500. Commodities: при ошибках GoldAPI/Alpha Vantage в ответе поле `error` (без mock-данных).
- Pipeline: marketplaces → discovery → scraping → виджеты; админ: POST `/api/admin/marketplaces/add-by-url`, POST `/api/admin/discovery/trigger-all`, GET `/api/pool/stats`.
- Модули: core, marketplaces, scraper, product_pool, market_data, dashboard, user_products, analytics, alerts, digests, ai_analyst.
- Ниже — исторический снимок; ориентир — разделы про модульную архитектуру и актуальные домены.

## Обзор

Imperecta — SaaS-платформа конкурентной разведки и рыночной аналитики для e-commerce. Отслеживает цены конкурентов на любых маркетплейсах (UniversalScraper), показывает рыночные данные (forex, крипто, сырьё, топливо, товары маркетплэйсов), генерирует ИИ-дайджесты и отправляет алерты при изменениях цен. Имеет встроенный ИИ для аналитики и обработки данных цен товаров на маркетплэйсах.  
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
| **products** | GET | /api/products/categories | Список категорий |
| **products** | GET | /api/products | Список товаров (пагинация) |
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
| **import** | POST | /api/import/products/preview | Превью импорта CSV |
| **import** | POST | /api/import/products/csv | Импорт CSV |
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
| **admin** | GET | /api/admin/marketplaces | Список маркетплейсов |
| **admin** | GET | /api/admin/marketplaces/{marketplace_id}/logs | Логи маркетплейса |
| **admin** | POST | /api/admin/marketplaces | Добавление маркетплейса |
| **admin** | DELETE | /api/admin/marketplaces/{marketplace_id} | Удаление маркетплейса |
| **admin** | GET | /api/admin/scrape-activity | Активность парсинга |
| **admin** | GET | /api/admin/error-distribution | Распределение ошибок |
| **admin** | GET | /api/admin/users | Список пользователей |
| **admin** | GET | /api/admin/claude-status | Статус Claude API |
| **admin** | POST | /api/admin/seed-products | Сид продуктов для теста парсинга (superuser) |
| **admin** | POST | /api/admin/trigger-scrape | Ручной запуск парсинга всех competitor_products |

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
| /products | ProductsPage | CRUD товаров |
| /products/:id | ProductDetailPage | Детали товара, график цен, конкуренты |
| /competitors | CompetitorsPage | CRUD конкурентов |
| /alerts | AlertsPage | CRUD алертов, события |
| /digests | DigestsPage | Список дайджестов |
| /import | ImportPage | Импорт CSV |
| /analytics | AnalyticsPage | Аналитика, тренды, прогнозы |
| /ai | AIAnalystRoute | AI-чат (locked для Trial/Free) |
| /settings | SettingsPage | Профиль, Telegram, план |
| /admin | AdminPage | Админ-панель (SuperuserRoute) |
| * | NotFoundPage | 404 |

---

## Технический стек

### Backend
- **Python 3.12** + **FastAPI** — REST API
- **SQLAlchemy 2.0 (async)** + **asyncpg** — ORM и подключение к PostgreSQL
- **SQLAlchemy (sync)** + **psycopg2** — sync_session_factory для Celery workers; ingest_market_data создаёт локальный async engine/session (не использует глобальный), чтобы избежать ошибки «different event loop» при повторном запуске
- **Alembic** — миграции БД
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

```
imperecta/
├── backend/
│   ├── alembic/
│   │   ├── env.py                    # Alembic env, async engine
│   │   └── versions/
│   │       ├── 001_initial_schema.py
│   │       ├── 002_update_user_language_default.py
│   │       ├── 003_telegram_user_fields.py
│   │       ├── 004_add_superuser_scrape_logs_admin_marketplaces_api_logs.py
│   │       ├── 005_add_user_last_login_at.py
│   │       ├── 006_add_ai_chat_tables.py
│   │       ├── 007_add_alert_ai_fields.py
│   │       ├── 007_add_performance_indexes.py
│   │       ├── 008_add_digest_type_ai_tone.py
│   │       ├── 009_add_user_avatar_url.py
│   │       ├── 010_extend_avatar_url_for_data_urls.py
│   │       ├── 011_reset_trial_ends_at.py
│   │       ├── 012_add_markets_tables.py
│   │       ├── 013_markets_refresh_log_metadata.py
│   │       ├── 014_avatar_url_text_preferred_country.py
│   │       └── .gitkeep
│   ├── alembic.ini                   # Alembic config
│   ├── app/
│   │   ├── api/
│   │   │   ├── admin.py               # Admin API (stats, marketplaces, users, claude-status)
│   │   │   ├── ai.py                 # AI chat API
│   │   │   ├── alerts.py             # Alerts CRUD, events, explanation, auto-response
│   │   │   ├── analytics.py          # Price history, comparison, forecast, benchmark
│   │   │   ├── auth.py               # Register, login, refresh, me, telegram-link
│   │   │   ├── competitors.py        # Competitors CRUD, products linking
│   │   │   ├── dashboard.py          # KPI, anomalies, aggregate-trend
│   │   │   ├── deps.py               # DbSession, get_current_user, get_current_superuser
│   │   │   ├── digests.py            # Digests list, detail
│   │   │   ├── import_export.py      # Auto-categorize, CSV import, template
│   │   │   ├── __init__.py           # api_router, include all routers
│   │   │   ├── markets.py            # Forex, crypto, commodities, ticker, overview, ingest
│   │   │   ├── products.py           # Products CRUD, categories, at-risk
│   │   │   └── telegram.py           # Webhook, generate-link-code, unlink, status
│   │   ├── config.py                 # Pydantic Settings (env vars; Decodo: decodo_api_url, decodo_username, decodo_password, decodo_enabled)
│   │   ├── database.py               # SQLAlchemy async engine, session, sync_session_factory (Celery)
│   │   ├── entitlements/
│   │   │   ├── __init__.py
│   │   │   └── plan.py               # ServiceTier, UserPlan, Feature, limits
│   │   ├── models/
│   │   │   ├── admin_marketplace.py  # AdminMarketplace (custom marketplaces)
│   │   │   ├── ai_chat.py            # AIChatSession, AIChatMessage
│   │   │   ├── alert_event.py        # AlertEvent
│   │   │   ├── alert.py              # Alert
│   │   │   ├── api_log.py            # ApiLog
│   │   │   ├── competitor_product.py # CompetitorProduct
│   │   │   ├── competitor.py         # Competitor
│   │   │   ├── digest.py             # Digest
│   │   │   ├── __init__.py
│   │   │   ├── markets_analytics.py  # MarketsCategoryAnalytics, MarketsMarketplaceAnalytics
│   │   │   ├── markets_opportunity.py# MarketsOpportunityBlock
│   │   │   ├── markets_overview.py   # MarketsOverviewItem
│   │   │   ├── markets_preferences.py# MarketsPreferences
│   │   │   ├── markets_refresh_log.py# MarketsRefreshLog, Status, Type
│   │   │   ├── markets_snapshots.py  # MarketsForex, Crypto, Commodity, TickerItem
│   │   │   ├── price_snapshot.py     # PriceSnapshot
│   │   │   ├── product.py            # Product
│   │   │   ├── scrape_log.py         # ScrapeLog
│   │   │   └── user.py               # User, UserPlan
│   │   ├── notifications/
│   │   │   ├── email_sender.py       # Resend email sending
│   │   │   ├── __init__.py
│   │   │   └── telegram_bot.py       # Telegram notifications
│   │   ├── schemas/
│   │   │   ├── ai_chat.py
│   │   │   ├── alert.py
│   │   │   ├── analytics.py
│   │   │   ├── competitor.py
│   │   │   ├── digest.py
│   │   │   ├── __init__.py
│   │   │   ├── markets.py            # error, cached в Crypto/CommoditiesResponse
│   │   │   ├── product.py
│   │   │   └── user.py
│   │   ├── scrapers/
│   │   │   ├── engine.py             # ScrapeResult, UniversalScraper; Decodo API primary, Playwright fallback
│   │   │   ├── __init__.py
│   │   │   └── proxy_manager.py      # Decodo (SmartProxy) rotating residential proxies
│   │   ├── services/
│   │   │   ├── admin_service.py      # ensure_superuser, marketplace ops
│   │   │   ├── market_data_service.py # Real-time forex, crypto, commodities, fuel; in-memory cache, graceful degradation (error/cached)
│   │   │   ├── ai_chat_service.py    # AI chat logic
│   │   │   ├── ai_service.py         # Claude API wrapper
│   │   │   ├── alert_ai_service.py   # Alert explanation, auto-response
│   │   │   ├── auth_service.py       # Auth, JWT, user ops
│   │   │   ├── benchmark_service.py  # Competitor benchmark
│   │   │   ├── claude_monitor.py     # Claude API health, stats
│   │   │   ├── dashboard_service.py  # KPI, anomalies, aggregate-trend
│   │   │   ├── forecast_service.py   # Price forecasting
│   │   │   ├── import_service.py     # CSV import, auto-categorize
│   │   │   ├── market_data/
│   │   │   │   ├── aggregate_service.py  # Category/marketplace analytics
│   │   │   │   ├── dto.py
│   │   │   │   ├── ingestion_service.py  # Ingest forex, crypto, commodities
│   │   │   │   ├── __init__.py
│   │   │   │   └── providers/
│   │   │   │       ├── base.py
│   │   │   │       ├── commodities_adapter.py
│   │   │   │       ├── crypto_adapter.py
│   │   │   │       ├── forex_adapter.py
│   │   │   │       ├── fuel_adapter.py
│   │   │   │       └── __init__.py
│   │   │   ├── markets_service.py    # Forex, crypto, commodities, ticker, overview (real price_snapshots)
│   │   │   ├── plan_limits.py        # Plan limits check
│   │   │   ├── price_service.py      # Price history, snapshots
│   │   │   ├── product_ai_service.py # AI recommendation
│   │   │   └── seed_service.py      # Seed products for scraping test (admin)
│   │   ├── workers/
│   │   │   ├── celery_app.py         # Celery app config
│   │   │   ├── alert_tasks.py        # check_alerts
│   │   │   ├── cleanup_tasks.py      # cleanup_old_data (30d snapshots/logs, 60d api_logs)
│   │   │   ├── digest_tasks.py       # schedule_weekly/daily_digests
│   │   │   ├── market_data_tasks.py  # ingest_market_data (fresh engine+session per task, avoids event loop error)
│   │   │   ├── scheduler.py          # Beat schedule
│   │   │   ├── scrape_tasks.py       # scrape_single (sync), scrape_all, price_snapshots + competitor_product
│   │   │   └── __init__.py
│   │   ├── __init__.py
│   │   └── main.py                   # FastAPI app, CORS, lifespan, routers
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
- `scraper/` — движок парсинга, discovery, pool scraping, tasks (`engine.py`, `discovery.py`, `service.py`, `tasks.py`, `api.py`).
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
- `celery_app.py` — создание и конфигурация Celery-приложения с includes на `modules/*/tasks.py`.
- `scheduler.py` — расписание периодических задач (beat) для task names из модулей.
- `cleanup_tasks.py` — очистка устаревших технических и ценовых данных.

### backend/alembic и backend/alembic/versions

- `alembic/env.py` — конфигурация окружения миграций (engine/session context).
- `001_initial_schema.py` — базовая схема БД.
- `002_update_user_language_default.py` — изменение default языка пользователя.
- `003_telegram_user_fields.py` — поля Telegram в `users`.
- `004_add_superuser_scrape_logs_admin_marketplaces_api_logs.py` — superuser, scrape_logs, admin_marketplaces, api_logs.
- `005_add_user_last_login_at.py` — timestamp последнего входа пользователя.
- `006_add_ai_chat_tables.py` — таблицы AI-чата.
- `007_add_alert_ai_fields.py` — AI-поля в сущностях алертов.
- `007_add_performance_indexes.py` — индексы для ускорения частых запросов.
- `008_add_digest_type_ai_tone.py` — типы дайджеста и тональность AI-контента.
- `009_add_user_avatar_url.py` — поле avatar URL пользователя.
- `010_extend_avatar_url_for_data_urls.py` — расширение размера поля avatar URL.
- `011_reset_trial_ends_at.py` — корректировка trial-периодов.
- `012_add_markets_tables.py` — таблицы подсистемы рыночных данных.
- `013_markets_refresh_log_metadata.py` — метаданные и доработки refresh log.
- `014_avatar_url_text_preferred_country.py` — avatar URL как TEXT + preferred country.
- `015_add_global_products_and_extend_marketplaces.py` — global pool + расширение admin marketplaces.
- `016_drop_digest_summary_json.py` — удаление неиспользуемой колонки `digests.summary_json`.

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

## Обновления архитектуры (PR-6)

### Новые backend-модули

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

### Удалено / вычищено

- `backend/app/services/seed_service.py` — удалён.
- `backend/app/models/markets_overview.py` — удалён (overview читает из `global_products`).
- Удалены мёртвые методы/импорты в `markets_service.py` и legacy overview materialization через `markets_overview`.

### Новые API routes

- `/api/pool/products`
- `/api/pool/marketplace-stats`
- `/api/pool/stats`
- `/api/pool/search`
- `/api/admin/marketplaces/add-by-url`
- `/api/admin/marketplaces/import-file`
- `/api/admin/discovery/trigger/{marketplace_id}`
- `/api/admin/discovery/trigger-all`
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

| Задача | Триггер | Описание |
|--------|---------|----------|
| scrape_single | API / scrape_all | Парсинг одного competitor_product: fetch → extract → price_snapshots → competitor_product.last_price → ScrapeLog |
| scrape_user_products | API | Парсинг всех товаров пользователя (stagger) |
| scrape_all | Beat каждые 6 ч | Очередь scrape_single для всех активных competitor_products |
| ingest_market_data | Beat каждые 2 ч | Загрузка forex, crypto, commodities; fresh engine+session per run (avoids asyncpg event loop error) |
| discover_all_marketplaces | Beat ежедневно 03:00 | Discovery URL товаров по активным маркетплейсам |
| scrape_all_pool_products | Beat каждые 6 ч | Массовый скрейпинг stale товаров из global pool |
| check_pool_completeness | Beat каждые 3 ч (:30) | Поиск и переочередь incomplete товаров в global pool |
| cleanup_old_data | Beat вс 04:00 | Удаление: price_snapshots/scrape_logs 30 дн, api_logs 60 дн |
| check_alerts | после scrape_single | Сравнение цен, email/Telegram |
| schedule_weekly_digests | Beat пт 18:00 | Еженедельные дайджесты |
| schedule_daily_digests | Beat ежедневно 08:00 | Ежедневные дайджесты (pro) |

---

## Текущий статус

- [x] Backend: FastAPI, Celery, scraper stack (extractors + scraper_pool + discovery_crawler), global product pool и discovery pipeline
- [x] Frontend: Landing, 15+ страниц, entitlements, AIAnalystRoute (locked), PlanLimitBanner
- [x] Auth: JWT, «Запомнить меня», telegram-link/disconnect в auth
- [x] Entitlements: Trial/Free/Paid Full, AI Analyst только для Paid
- [x] Миграции 001–016 (включая global_products/global_price_snapshots/discovery_logs и удаление `digests.summary_json`)
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
