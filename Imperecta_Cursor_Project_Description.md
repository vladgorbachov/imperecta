# Imperecta — Описание проекта для Cursor IDE

## Обзор

Imperecta — SaaS-платформа конкурентной разведки для e-commerce. Отслеживает цены конкурентов на маркетплейсах (Ozon, Wildberries, Kaspi), генерирует ИИ-дайджесты и отправляет алерты при изменениях цен.

Целевая аудитория: малый и средний e-commerce бизнес в СНГ (Россия, Казахстан, Украина, Молдова).

---

## Технический стек

### Backend
- **Python 3.12** + **FastAPI** — REST API
- **SQLAlchemy 2.0 (async)** + **asyncpg** — ORM и подключение к PostgreSQL
- **Alembic** — миграции БД
- **Celery** + **Redis** — фоновые задачи (парсинг, алерты, дайджесты)
- **Playwright** — headless-браузер для парсинга JS-rendered страниц (Ozon)
- **BeautifulSoup + httpx** — парсинг статических сайтов
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
- **Sonner** — toast-уведомления
- **next-themes** — переключение темы (light/dark, по умолчанию dark)

### Безопасность
- **Snyk** — сканирование зависимостей и кода
- **Bandit** — статический анализ Python-кода
- **pip-audit** + **Safety** — проверка уязвимостей в Python-пакетах
- **Gitleaks** — поиск утёкших секретов в git-истории
- **eslint-plugin-security** — безопасность frontend-кода

---

## Облачная инфраструктура

### Схема связей

```
┌──────────────────────────────────────────────────────────────────┐
│                        ПОЛЬЗОВАТЕЛЬ                              │
│                     (браузер / Telegram)                          │
└──────────┬───────────────────────────────────┬───────────────────┘
           │ HTTPS                              │ Telegram API
           ▼                                    ▼
┌─────────────────────┐              ┌─────────────────────┐
│  CLOUDFLARE PAGES   │              │   TELEGRAM BOT API  │
│                     │              │   (api.telegram.org) │
│  React SPA (Vite)   │              └──────────┬──────────┘
│  imperecta.pages.dev│                         │
└──────────┬──────────┘                         │
           │ HTTPS (VITE_API_URL)               │ webhook
           ▼                                    ▼
┌──────────────────────────────────────────────────────────────────┐
│                     RAILWAY (3 сервиса)                          │
│                                                                  │
│  ┌──────────────────────────────────────────┐                    │
│  │  imperecta (backend)                     │                    │
│  │  FastAPI API server                      │                    │
│  │  imperecta-production.up.railway.app     │◄───── Cloudflare   │
│  │                                          │       Pages        │
│  │  Start: uvicorn app.main:app             │                    │
│  │         --host 0.0.0.0 --port $PORT      │                    │
│  └────┬──────────┬──────────┬───────────────┘                    │
│       │          │          │                                    │
│  ┌────▼────┐ ┌───▼────┐ ┌──▼──────────────────────┐             │
│  │ Celery  │ │ Celery │ │  Scrapers               │             │
│  │ Worker  │ │ Beat   │ │  (Playwright + httpx)    │             │
│  │         │ │        │ │                          │             │
│  │ Задачи: │ │ Cron:  │ │  Targets:               │             │
│  │-scrape  │ │-каждые │ │  - ozon.ru              │             │
│  │-alerts  │ │ 6 часов│ │  - wildberries.ru       │             │
│  │-digests │ │-weekly │ │  - kaspi.kz             │             │
│  │-email   │ │-daily  │ │  - custom websites      │             │
│  │-cleanup │ │-cleanup│ │                          │             │
│  └─────────┘ └────────┘ └──────────────────────────┘             │
│                                                                  │
└───────┬──────────────┬──────────────┬───────────────┬────────────┘
        │              │              │               │
        ▼              ▼              ▼               ▼
┌──────────────┐ ┌───────────┐ ┌───────────┐ ┌──────────────┐
│   SUPABASE   │ │  UPSTASH  │ │ ANTHROPIC │ │    RESEND    │
│  PostgreSQL  │ │   Redis   │ │ Claude API│ │  Email API   │
└──────────────┘ └───────────┘ └───────────┘ └──────────────┘
```

### Описание каждого сервиса

#### 1. Cloudflare Pages (Frontend)
- **URL:** `https://imperecta.pages.dev`
- **Деплой:** автоматический при push в `main`
- **Build command:** `cd frontend && npm install && npm run build`
- **Env:** `VITE_API_URL` → URL Railway backend

#### 2. Railway — сервис `imperecta` (Backend API)
- **URL:** `https://imperecta-production.up.railway.app`
- **Root Directory:** `backend`
- **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Lifespan:** create_all (таблицы), setup Telegram webhook, ensure_superuser

#### 3. Railway — сервис `celery-worker`
- **Start Command:** `celery -A app.workers.celery_app worker -l info -c 2`
- **Задачи:** scrape_single, scrape_user_products, scrape_all, check_alerts, generate_weekly_digest, generate_daily_digest, cleanup_old_data

#### 4. Railway — сервис `celery-beat`
- **Start Command:** `celery -A app.workers.celery_app beat -l info`
- **Расписание:**
  - `scrape_all` — каждые 6 часов
  - `schedule_weekly_digests` — пятница 18:00 UTC
  - `schedule_daily_digests` — ежедневно 08:00 UTC
  - `cleanup_old_data` — воскресенье 04:00 UTC

#### 5. Supabase (PostgreSQL)
- **Connection:** Transaction Pooler (PgBouncer), порт 6543
- **Таблицы:** users, products, competitors, competitor_products, price_snapshots, alerts, alert_events, digests, scrape_logs, admin_marketplaces, api_logs, ai_chat_sessions, ai_chat_messages

#### 6. Upstash (Redis)
- **Функции:** Celery broker, Celery result backend

#### 7. Anthropic Claude API
- **Модель:** claude-sonnet-4-20250514 (CLAUDE_MODEL)
- **Использование:** дайджесты, AI-чат, авто-категоризация товаров, объяснения алертов, авто-ответы на алерты

#### 8. Resend (Email)
- **Отправитель:** `noreply@imperecta.com`

#### 9. Telegram Bot API
- **Бот:** @ImperectaBot
- **Webhook:** /api/telegram/webhook (устанавливается при старте backend)
- **Команды:** /start, /status, /help

#### 10. GitHub
- **Репо:** `vladgorbachov/imperecta`
- **CI:** GitHub Actions — ruff, pytest, eslint, build, security (bandit, safety, pip-audit, gitleaks, snyk)

#### 11. Sentry
- **Подключение:** SENTRY_DSN в Railway env

---

## Переменные окружения

```
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=rediss://...
JWT_SECRET=...
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=30
JWT_REFRESH_EXPIRATION_DAYS=7
JWT_REFRESH_EXPIRATION_DAYS_REMEMBER=30
CLAUDE_API_KEY=...
CLAUDE_MODEL=claude-sonnet-4-20250514
RESEND_API_KEY=...
EMAIL_FROM=noreply@imperecta.com
TELEGRAM_BOT_TOKEN=...
SENTRY_DSN=...
PROXY_LIST=
APP_ENV=production
APP_URL=https://imperecta-production.up.railway.app
ALLOWED_ORIGINS=https://imperecta.pages.dev
PORT=8000
```

---

## Структура проекта

```
imperecta/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entrypoint, CORS, Sentry, lifespan
│   │   ├── config.py            # Pydantic Settings
│   │   ├── database.py          # SQLAlchemy async engine, session, Base
│   │   ├── models/              # User, UserPlan, Product, Competitor, CompetitorProduct,
│   │   │                         # PriceSnapshot, Alert, AlertEvent, Digest,
│   │   │                         # ScrapeLog, AdminMarketplace, ApiLog,
│   │   │                         # AIChatSession, AIChatMessage
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── api/                 # auth, telegram, products, competitors, analytics,
│   │   │                         # alerts, digests, import_export, dashboard, admin, ai
│   │   ├── services/            # auth, price, alert, digest, ai_chat, product_ai,
│   │   │                         # alert_ai, import, admin, claude_monitor, dashboard
│   │   ├── scrapers/            # engine (Ozon, WB, GenericWebScraper), proxy_manager
│   │   ├── workers/             # celery_app, scrape_tasks, alert_tasks, digest_tasks,
│   │   │                         # scheduler, cleanup_tasks
│   │   ├── notifications/       # email_sender, telegram_bot
│   │   └── entitlements/        # plan (ServiceTier, Feature, limits)
│   ├── alembic/versions/        # 001–011: initial, user_language, telegram,
│   │                            # superuser+scrape_logs+admin_marketplaces+api_logs,
│   │                            # last_login_at, ai_chat, performance_indexes,
│   │                            # digest_type+ai_tone, user_avatar_url,
│   │                            # avatar_url_extend, reset_trial_ends_at
│   ├── tests/
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── security.cfg
├── frontend/
│   ├── src/
│   │   ├── api/                 # client, setupAuth, auth, admin, products, competitors,
│   │   │                         # analytics, alerts, digests, import, ai
│   │   ├── lib/                 # utils, authStorage, authCookie, formatters
│   │   ├── hooks/               # useAuth, useProducts, useCompetitors, useAnalytics,
│   │   │                         # useAlerts, useAdmin, useDashboard, useEntitlements,
│   │   │                         # usePlanLimits, useSidebar, useDebounce
│   │   ├── components/          # layout (Header, Sidebar, MobileSidebar, BottomNavigation,
│   │   │                         # DashboardLayout), dashboard, charts, products,
│   │   │                         # ui (shadcn), auth, ai (ChatInput, PresetQuestions),
│   │   │                         # ProtectedRoute, SuperuserRoute, ChangePasswordRoute,
│   │   │                         # PublicAuthRoute, AIAnalystRoute, SessionExpiryWarning,
│   │   │                         # PlanLimitBanner, LoadingScreen
│   │   ├── pages/               # Login, Register, ForgotPassword, ForcePasswordChange,
│   │   │                         # Dashboard, Products, ProductDetail, Competitors,
│   │   │                         # Alerts, Digests, Import, Analytics, AIAnalyst,
│   │   │                         # AdminPage, Settings, NotFound, landing/LandingPage
│   │   ├── stores/              # authStore (Zustand)
│   │   ├── i18n/
│   │   └── types/
│   ├── public/locales/          # en, ru, ar, zh, es, fr, uk, ro
│   ├── vite.config.ts
│   └── package.json
├── e2e/                         # Playwright: smoke.spec, auth.spec, dashboard.spec
├── docker-compose.yml           # postgres, redis, backend, celery-worker, celery-beat, frontend
├── .github/workflows/ci.yml
└── Imperecta_Cursor_Project_Description.md
```

---

## Функционал

### Backend API (REST)

| Модуль | Endpoints |
|--------|-----------|
| **auth** | POST /register, /login, /refresh, /change-initial-password, /telegram-link, /telegram-disconnect; GET/PUT /me |
| **telegram** | POST /webhook; POST /generate-link-code, /unlink; GET /status |
| **products** | GET /categories, /, /at-risk, /{id}, /{id}/ai-recommendation; POST /; PUT/DELETE /{id} |
| **competitors** | GET/POST /; PUT/DELETE /{id}; POST /products; GET /products/{product_id}, /{competitor_id}/products; DELETE /products/{id} |
| **analytics** | GET /products/{id}/price-history, /comparison, /forecast; GET /market-forecast; POST /simulate, /advanced-simulation; GET /competitor-benchmark, /comparison-matrix, /dashboard/summary, /dashboard/anomalies |
| **dashboard** | GET /kpi, /anomalies, /market-overview, /aggregate-trend |
| **alerts** | GET/POST /; PUT/DELETE /{id}; GET /events; GET /events/{event_id}/explanation; POST /events/{event_id}/auto-response |
| **digests** | GET /, /{id} |
| **import** | POST /auto-categorize, /products/preview, /products/csv; GET /products/template |
| **ai** | POST /chat; GET /sessions, /sessions/{id}; DELETE /sessions/{id} |
| **admin** (superuser) | GET /stats, /marketplaces, /marketplaces/{id}/logs, /scrape-activity, /error-distribution, /users, /claude-status; POST /marketplaces; DELETE /marketplaces/{id} |

**Health:** GET /health (liveness), GET /api/health (DB + Redis)

### Entitlements (планы и лимиты)

| ServiceTier | UserPlan | Products | Competitors | AI Analyst |
|-------------|----------|----------|-------------|------------|
| Trial | trial | 999 | 999 | нет |
| Free | starter | 50 | 15 | нет |
| Paid Full | business, pro | 999 | 999 | да |

- **Trial:** 14 дней (trial_ends_at при регистрации)
- **is_trial_expired:** проверка trial_ends_at
- **get_entitlements_for_frontend:** tier, features, limits, trial_duration_days, is_trial_expired

### Frontend страницы

| Маршрут | Страница | Функционал |
|---------|----------|------------|
| /ai.market.intelligence.agent | LandingPage | Публичный лендинг (редирект на / при авторизации) |
| /login, /register, /forgot-password | LoginPage, RegisterPage, ForgotPasswordPage | Аутентификация |
| /change-password | ForcePasswordChangePage (ChangePasswordRoute) | Смена пароля суперюзера |
| /dashboard | DashboardPage | KPI, MarketDataTable, CompetitorBenchmark, AnomalyFeed, ScenarioSimulator |
| /products | ProductsPage | CRUD товаров, категории, поиск, пагинация, импорт CSV |
| /products/:id | ProductDetailPage | График цен, конкуренты, алерты, AI-рекомендация |
| /competitors | CompetitorsPage | CRUD конкурентов, привязка товаров |
| /alerts | AlertsPage | CRUD алертов, события, объяснения, авто-ответы |
| /digests | DigestsPage | Список дайджестов |
| /import | ImportPage | Импорт CSV, preview, авто-категоризация |
| /analytics | AnalyticsPage | Тренды, прогнозы, матрица сравнения |
| /ai | AIAnalystRoute | AI-чат (locked для Trial/Free) |
| /admin | AdminPage | Админ-панель (superuser) |
| /settings | SettingsPage | Профиль, аватар, Telegram, план |

### Sidebar и навигация

- **Секции:** Core (Dashboard, Products, Competitors), Market Intelligence (Analytics, AI Analyst), Tools (Alerts, Digests, Import), Account (Settings), Admin (superuser)
- **Desktop:** Collapsible Sidebar (localStorage «imperecta_sidebar_collapsed»)
- **Mobile:** Hamburger → Sheet, BottomNavigation (Dashboard, Products, Analytics, AI, Alerts)
- **Trial footer:** прогресс-бар trial_ends_at, кнопка Upgrade

### Celery задачи

| Задача | Триггер | Описание |
|--------|---------|----------|
| scrape_single | API | Парсинг одного competitor_product |
| scrape_user_products | API | Парсинг всех товаров пользователя |
| scrape_all | Beat каждые 6 ч | Парсинг всех активных пользователей |
| cleanup_old_data | Beat вс 04:00 | Удаление: price_snapshots 180d, scrape_logs 90d, api_logs 60d, ai_chat_messages 365d, alert_events 180d |
| check_alerts | после scrape_single | Сравнение цен, email/Telegram |
| schedule_weekly_digests | Beat пт 18:00 | Еженедельные дайджесты |
| schedule_daily_digests | Beat ежедневно 08:00 | Ежедневные дайджесты (pro) |

### E2E (Playwright)

- **smoke.spec:** frontend loads, login page, API health, /docs
- **auth.spec:** регистрация, логин
- **dashboard.spec:** дашборд после логина

---

## Текущий статус

- [x] Backend: FastAPI, все API-роуты, Celery, scrapers (Ozon, WB, Kaspi, Generic)
- [x] Frontend: Landing, 15+ страниц, entitlements, AIAnalystRoute (locked), PlanLimitBanner
- [x] Auth: JWT, «Запомнить меня», telegram-link/disconnect в auth
- [x] Entitlements: Trial/Free/Paid Full, AI Analyst только для Paid
- [x] Миграции 001–011
- [x] Локальная разработка: docker-compose
- [x] CI: ruff, pytest, eslint, build, security
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
