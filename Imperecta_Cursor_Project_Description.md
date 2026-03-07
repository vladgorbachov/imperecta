# Imperecta — Описание проекта для Cursor IDE

## Обзор

Imperecta — SaaS-платформа конкурентной разведки для e-commerce. Отслеживает цены конкурентов на маркетплейсах (Ozon, Wildberries), генерирует ИИ-дайджесты и отправляет алерты при изменениях цен.

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
- **Anthropic Claude API** — генерация ИИ-дайджестов на русском языке
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
- **Axios** — HTTP-клиент
- **react-i18next** — локализация (ru.json, en.json)
- **Sonner** — toast-уведомления
- **next-themes** — переключение темы (light/dark)

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
           │ HTTPS (VITE_API_URL)               │ webhook/polling
           ▼                                    ▼
┌──────────────────────────────────────────────────────────────────┐
│                     RAILWAY (3 сервиса)                          │
│                                                                  │
│  ┌──────────────────────────────────────────┐                    │
│  │  imperecta (backend)                     │                    │
│  │  FastAPI API server                      │                    │
│  │  imperecta-production.up.railway.app     │◄───── Cloudflare   │
│  │                                          │       Pages        │
│  │  Start: alembic upgrade head &&          │                    │
│  │         uvicorn app.main:app             │                    │
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
│  │-digests │ │-weekly │ │  - custom websites      │             │
│  │-email   │ │ digest │ │                          │             │
│  └─────────┘ └────────┘ └──────────────────────────┘             │
│                                                                  │
└───────┬──────────────┬──────────────┬───────────────┬────────────┘
        │              │              │               │
        ▼              ▼              ▼               ▼
┌──────────────┐ ┌───────────┐ ┌───────────┐ ┌──────────────┐
│   SUPABASE   │ │  UPSTASH  │ │ ANTHROPIC │ │    RESEND    │
│  PostgreSQL  │ │   Redis   │ │ Claude API│ │  Email API   │
│              │ │           │ │           │ │              │
│ Хранение:   │ │ Функции:  │ │ Функции:  │ │ Функции:     │
│ - users      │ │ - Celery  │ │ - Weekly/ │ │ - Alert      │
│ - products   │ │   broker  │ │   daily   │ │   emails     │
│ - competitors│ │ - Celery  │ │   digests │ │ - Digest     │
│ - prices     │ │   results │ │ - Price   │ │   emails     │
│ - snapshots  │ │ - Cache   │ │   analysis│ │              │
│ - alerts     │ │ - Rate    │ │ - Russian │ │ noreply@     │
│ - digests    │ │   limiting│ │   language │ │ imperecta.com│
│              │ │           │ │           │ │              │
│ Host:        │ │ Host:     │ │ Endpoint: │ │ Endpoint:    │
│ pooler.      │ │ eu1-xxx.  │ │ api.      │ │ api.         │
│ supabase.com │ │ upstash.io│ │ anthropic │ │ resend.com   │
│ Port: 6543   │ │ Port: 6379│ │ .com      │ │              │
└──────────────┘ └───────────┘ └───────────┘ └──────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                    ДОПОЛНИТЕЛЬНЫЕ СЕРВИСЫ                        │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │    GITHUB    │  │    SENTRY    │  │     SNYK     │           │
│  │              │  │              │  │              │           │
│  │ Репозиторий: │  │ Мониторинг:  │  │ Безопасность:│           │
│  │ vladgorbachov│  │ - Ошибки     │  │ - CVE scan   │           │
│  │ /imperecta   │  │ - Трейсы     │  │ - Code scan  │           │
│  │              │  │ - Алерты     │  │ - Auto PRs   │           │
│  │ CI/CD:       │  │              │  │              │           │
│  │ - Push→deploy│  │ DSN →        │  │ Token →      │           │
│  │   (Railway + │  │ Railway env  │  │ GitHub       │           │
│  │   Cloudflare)│  │              │  │ Secrets      │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
└──────────────────────────────────────────────────────────────────┘
```

### Описание каждого сервиса

#### 1. Cloudflare Pages (Frontend)
- **Что:** Хостинг React SPA
- **URL:** `https://imperecta.pages.dev`
- **Деплой:** автоматический при push в `main` (собирает `frontend/dist`)
- **Build command:** `cd frontend && npm install && npm run build`
- **Env:** `VITE_API_URL` → URL Railway backend
- **Связь:** отправляет HTTP-запросы к Railway backend через `VITE_API_URL`

#### 2. Railway — сервис `imperecta` (Backend API)
- **Что:** FastAPI сервер, обрабатывает все API-запросы
- **URL:** `https://imperecta-production.up.railway.app`
- **Root Directory:** `backend`
- **Сборка:** Dockerfile на Python 3.12-slim, Playwright Chromium; для Railway можно использовать `mcr.microsoft.com/playwright/python:v1.58.0-noble` при проблемах со сборкой.
- **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT` (таблицы создаются через `create_all` в lifespan; для миграций — `alembic upgrade head` отдельно)
- **Связи:**
  - ← принимает запросы от Cloudflare Pages (CORS: `ALLOWED_ORIGINS`)
  - → подключается к Supabase PostgreSQL (`DATABASE_URL`)
  - → подключается к Upstash Redis (`REDIS_URL`)
  - → вызывает Anthropic Claude API (`CLAUDE_API_KEY`)
  - → отправляет email через Resend (`RESEND_API_KEY`)
  - → отправляет сообщения через Telegram Bot API (`TELEGRAM_BOT_TOKEN`)

#### 3. Railway — сервис `celery-worker` (Фоновые задачи)
- **Что:** Celery worker — выполняет фоновые задачи
- **Start Command:** `celery -A app.workers.celery_app worker -l info -c 2`
- **Задачи:**
  - `scrape_single` — парсинг одного конкурентного товара
  - `scrape_user_products` — парсинг всех товаров пользователя
  - `scrape_all` — парсинг всех активных пользователей
  - `check_alerts` — проверка алертов после парсинга
  - `generate_weekly_digest` — генерация еженедельного ИИ-дайджеста
  - `generate_daily_digest` — генерация ежедневного дайджеста (pro)
- **Связи:**
  - ↔ получает задачи из Upstash Redis (broker)
  - → подключается к Supabase PostgreSQL (чтение/запись данных)
  - → парсит ozon.ru, wildberries.ru, custom сайты (через Playwright/httpx)
  - → вызывает Claude API для дайджестов
  - → отправляет алерты через Resend и Telegram

#### 4. Railway — сервис `celery-beat` (Планировщик)
- **Что:** Celery Beat — запускает задачи по расписанию
- **Start Command:** `celery -A app.workers.celery_app beat -l info`
- **Расписание:**
  - `scrape_all` — каждые 6 часов
  - `generate_weekly_digest` — пятница 18:00 UTC
  - `generate_daily_digest` — ежедневно 08:00 UTC (для pro-пользователей)
  - `cleanup_old_snapshots` — раз в неделю (удаление данных старше 90 дней)
- **Связи:**
  - → отправляет задачи в Upstash Redis (broker)

#### 5. Supabase (PostgreSQL)
- **Что:** Основная база данных
- **Connection:** Transaction Pooler (PgBouncer), порт 6543
- **Таблицы:** users, products, competitors, competitor_products, price_snapshots, alerts, alert_events, digests, scrape_logs, admin_marketplaces, api_logs
- **Кто подключается:** backend (imperecta), celery-worker, alembic (миграции при деплое)

#### 6. Upstash (Redis)
- **Что:** Брокер сообщений для Celery + кеш
- **Connection:** TLS (`rediss://`), порт 6379
- **Функции:**
  - Celery broker — очередь задач между beat → worker
  - Celery result backend — хранение результатов задач
  - Кеширование данных дашборда (будущее)
  - Rate limiting для API (будущее)
- **Кто подключается:** backend, celery-worker, celery-beat

#### 7. Anthropic Claude API
- **Что:** ИИ для генерации дайджестов
- **Endpoint:** `https://api.anthropic.com/v1/messages`
- **Модель:** по умолчанию claude-sonnet-4-20250514 (настраивается через `CLAUDE_MODEL`, без жёсткой привязки к версии)
- **Использование:** celery-worker вызывает при генерации дайджестов; все вызовы логируются в api_logs
- **Мониторинг:** claude_monitor (health check), GET /api/admin/claude-status (для superuser)
- **Язык вывода:** русский

#### 8. Resend (Email)
- **Что:** Отправка email-уведомлений
- **Endpoint:** `https://api.resend.com/emails`
- **Отправитель:** `noreply@imperecta.com`
- **Типы писем:** алерты о изменении цен, еженедельные дайджесты

#### 9. Telegram Bot API
- **Что:** Алерты и дайджесты в Telegram, привязка аккаунта
- **Бот:** @ImperectaBot
- **Функции:** webhook для входящих сообщений, генерация кода привязки, отвязка, статус
- **API:** POST /api/telegram/webhook, /generate-link-code, /unlink; GET /api/telegram/status
- **Webhook:** автоматически устанавливается при старте backend (lifespan)
- **Модель User:** telegram_chat_id, telegram_link_code (миграция 003)
- **Вызывается из:** celery-worker (алерты), backend (webhook, привязка)

#### 10. GitHub
- **Что:** Репозиторий + CI/CD
- **Репо:** `vladgorbachov/imperecta`
- **CI:** GitHub Actions — ci.yml (lint, test, build, security)
- **CD:** push в main → автодеплой Railway + Cloudflare Pages

#### 11. Sentry
- **Что:** Мониторинг ошибок
- **Подключение:** через `SENTRY_DSN` в Railway env
- **Интеграция:** middleware в FastAPI

#### 12. Snyk
- **Что:** Сканирование безопасности
- **Интеграция:** GitHub (автоматические PR с фиксами), GitHub Actions

---

## Переменные окружения (все 3 Railway-сервиса)

```
DATABASE_URL=postgresql+asyncpg://postgres.xxx:PASSWORD@aws-1-eu-central-2.pooler.supabase.com:6543/postgres
REDIS_URL=rediss://default:PASSWORD@eu1-xxx.upstash.io:6379
JWT_SECRET=<generated-secret-48-chars>
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=30
JWT_REFRESH_EXPIRATION_DAYS=7
JWT_REFRESH_EXPIRATION_DAYS_REMEMBER=30
JWT_REFRESH_EXPIRATION_DAYS_REMEMBER=30
CLAUDE_API_KEY=sk-ant-api03-xxx
CLAUDE_MODEL=claude-sonnet-4-20250514
RESEND_API_KEY=re_xxx
EMAIL_FROM=noreply@imperecta.com
TELEGRAM_BOT_TOKEN=123:AAA-xxx
SENTRY_DSN=https://xxx@o123.ingest.sentry.io/456
PROXY_LIST=
APP_ENV=production
APP_URL=https://imperecta.pages.dev
ALLOWED_ORIGINS=https://imperecta.pages.dev
PORT=8000
```

---

## Структура проекта

```
imperecta/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entrypoint, CORS, Sentry, lifespan (create_all, ensure_superuser)
│   │   ├── config.py            # Pydantic Settings (env vars)
│   │   ├── database.py          # SQLAlchemy async engine, session, Base
│   │   ├── models/              # User, UserPlan, Product, Competitor, CompetitorProduct,
│   │   │                         # PriceSnapshot, Alert, AlertEvent, Digest,
│   │   │                         # ScrapeLog, AdminMarketplace, ApiLog
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── api/                 # auth, telegram, products, competitors, analytics,
│   │   │                         # alerts, digests, import_export, admin (superuser only)
│   │   ├── services/            # auth, price, alert, digest, ai, import, admin, claude_monitor
│   │   ├── scrapers/            # engine (Ozon, WB, GenericWebScraper, ScraperFactory), proxy_manager
│   │   ├── workers/             # celery_app, scrape_tasks, alert_tasks, digest_tasks, scheduler
│   │   └── notifications/       # email_sender, telegram_bot
│   ├── alembic/                 # migrations 001–005: initial, user_language, telegram, superuser+scrape_logs+admin_marketplaces+api_logs, last_login_at
│   ├── tests/                   # pytest (conftest, test_health)
│   ├── requirements.txt
│   ├── Dockerfile               # uvicorn only; tables via create_all in lifespan
│   ├── pyproject.toml          # ruff, pytest config
│   └── security.cfg             # Bandit config
├── frontend/
│   ├── src/
│   │   ├── api/                 # client.ts, setupAuth.ts (interceptors), auth, admin,
│   │   │                         # products, competitors, analytics, alerts, digests, import
│   │   ├── lib/                 # utils.ts, authStorage.ts (localStorage/sessionStorage)
│   │   ├── hooks/               # useAuth, useProducts, useCompetitors, useAnalytics, useAlerts, useAdmin
│   │   ├── components/          # layout (Header, Sidebar, MobileSidebar, DashboardLayout), charts,
│   │   │                         # products (FiltersPanel), tables, ui (shadcn, collapsible),
│   │   │                         # auth (AuthLayout, AuthProvider), ProtectedRoute, SuperuserRoute,
│   │   │                         # ChangePasswordRoute, SessionExpiryWarning, StubPage
│   │   ├── pages/               # Login, Register, ForgotPassword, ForcePasswordChange, Dashboard,
│   │   │                         # Products, ProductDetail, Competitors, Alerts, Digests, Import,
│   │   │                         # Analytics (заглушка), AdminPage (superuser), Settings, NotFound
│   │   ├── stores/              # authStore (Zustand)
│   │   ├── i18n/                # ru.json, en.json, index.ts
│   │   ├── data/                # mockFilters, mock data
│   │   └── types/               # filters, shared types
│   ├── vite.config.ts           # proxy /api → localhost:8000
│   └── package.json
├── docker-compose.yml           # postgres, redis, backend, celery-worker, celery-beat, frontend
├── docker-compose.prod.yml
├── wrangler.jsonc               # Cloudflare (assets: frontend)
├── .github/workflows/ci.yml     # ruff, pytest, eslint, build, security (bandit, safety, pip-audit, gitleaks, snyk)
└── README.md
```

---

## Функционал

### Backend API (REST)

| Модуль | Endpoints |
|--------|-----------|
| **auth** | POST /register, /login, /refresh, /change-initial-password; GET/PUT /me |
| **telegram** | POST /webhook (Telegram callback); POST /generate-link-code, /unlink; GET /status |
| **products** | GET /categories, GET/POST /, GET/PUT/DELETE /{id} |
| **competitors** | GET/POST /; PUT/DELETE /{id}; POST /products; GET /products/{product_id}, /{competitor_id}/products; DELETE /products/{id} |
| **analytics** | GET /products/{id}/price-history, /products/{id}/comparison; GET /dashboard/summary, /dashboard/anomalies |
| **alerts** | GET/POST /; PUT/DELETE /{id}; GET /events |
| **digests** | GET /, /{id} |
| **import** | POST /products/preview, /products/csv; GET /products/template |
| **admin** (superuser) | GET /stats, /marketplaces, /marketplaces/{id}/logs, /scrape-activity, /error-distribution, /users, /claude-status; POST /marketplaces; DELETE /marketplaces/{id} |

**Health:** GET /health (liveness), GET /api/health (DB + Redis check)

**Реестр маркетплейсов (admin_marketplaces):** дополняет встроенный реестр (Ozon, WB, Kaspi, Custom). Суперюзер добавляет кастомные маркетплейсы через POST /admin/marketplaces. Celery worker обновляет last_scrape_at, total/successful/failed_scrapes при каждом scrape_single.

### Frontend страницы

| Маршрут | Страница | Функционал |
|---------|----------|------------|
| /login, /register, /forgot-password, /change-password | LoginPage, RegisterPage, ForgotPasswordPage, ForcePasswordChangePage | Аутентификация, JWT, «Запомнить меня», смена пароля суперюзера |
| /dashboard | DashboardPage | Сводка: товары, конкуренты, алерты, изменения цен; аномалии |
| /products | ProductsPage | CRUD товаров, категории, поиск, пагинация, импорт CSV |
| /products/:id | ProductDetailPage | График цен (7d/30d/90d), конкуренты, алерты |
| /competitors | CompetitorsPage | CRUD конкурентов (Ozon, WB, Kaspi, Custom), привязка товаров |
| /alerts | AlertsPage | CRUD алертов (price_drop, price_increase, out_of_stock, new_promo), каналы (email, telegram, both) |
| /digests | DigestsPage | Список дайджестов, просмотр |
| /import | ImportPage | Импорт товаров из CSV, preview, шаблон |
| /analytics | AnalyticsPage | Заглушка «Раздел в разработке» |
| /admin | AdminPage | Админ-панель (только superuser): статистика, маркетплейсы, парсинг, Claude API, пользователи |
| /settings | SettingsPage | Профиль (name, company_name), привязка Telegram |

### Sidebar и навигация

- **Аналитика** (BarChart3) → /analytics — видна всем пользователям
- **Администрирование** (Shield) → /admin — видна только при `user.is_superuser === true`
- Остальные пункты: Dashboard, Products, Competitors, Alerts, Digests, Import, Settings

### Аутентификация и сессии

| Функция | Описание |
|--------|----------|
| **JWT** | access_token 30 мин, refresh_token 7 или 30 дней |
| **Запомнить меня** | При включении: refresh 30 дней, localStorage. При выключении: refresh 7 дней, sessionStorage |
| **Суперюзер** | admin@imperecta.com / admin (при первом запуске), is_superuser, force_password_change |
| **Смена пароля** | POST /change-initial-password — обязательна при первом входе суперюзера |
| **SessionExpiryWarning** | Pop-up за 3 дня до истечения сессии (persistent), при истечении — принудительный re-login |

### Celery задачи

| Задача | Триггер | Описание |
|--------|---------|----------|
| scrape_single | API / вручную | Парсинг одного competitor_product, логирование в scrape_logs, проверка алертов |
| scrape_user_products | API | Парсинг всех товаров пользователя |
| scrape_all | Beat каждые 6 ч | Парсинг всех активных пользователей |
| cleanup_old_snapshots | Beat вс 03:00 | Удаление данных старше 90 дней |
| check_alerts | после scrape_single | Сравнение цен, отправка email/Telegram |
| schedule_weekly_digests | Beat пт 18:00 | Генерация еженедельных дайджестов (Claude) |
| schedule_daily_digests | Beat ежедневно 08:00 | Генерация ежедневных дайджестов (pro) |

---

## Текущий статус

- [x] Код сгенерирован (12 промптов MVP + 4 промпта cloud-адаптации)
- [x] GitHub репозиторий создан
- [x] Supabase PostgreSQL создан
- [x] Upstash Redis создан
- [x] Railway: 3 сервиса созданы, переменные заданы
- [x] Cloudflare Pages подключён
- [x] Snyk подключён
- [x] Backend: FastAPI, все API-роуты (включая telegram), Celery tasks, scrapers (engine: Ozon, WB, generic, ScraperFactory)
- [x] Frontend: 15 страниц (Dashboard, Products, ProductDetail, Competitors, Alerts, Digests, Import, Analytics, AdminPage, Settings, Login, Register, ForgotPassword, ForcePasswordChange, NotFound), FiltersPanel, collapsible, SessionExpiryWarning
- [x] Backend: суперюзер, Admin API, scrape_logs, admin_marketplaces, api_logs, логирование Claude API
- [x] Auth: «Запомнить меня», persistent-сессии (localStorage/sessionStorage), restoreSession при загрузке, 401 auto-refresh
- [x] Локальная разработка: docker-compose (postgres, redis, backend, celery-worker, celery-beat, frontend)
- [x] CI: ruff, pytest, eslint, build, security (bandit, safety, pip-audit, gitleaks, snyk)
- [ ] Успешный деплой backend (Railway)
- [ ] Успешный деплой frontend (Cloudflare)
- [ ] E2E проверка (регистрация → добавление товара → парсинг)
- [ ] Closed beta с 15 респондентами

---

## Правила для Cursor

- Все комментарии в коде и имена переменных, функций, классов — **только на английском**
- UI тексты — на русском языке
- Не делать ничего сверх того, что запрошено
- При изменении backend — не трогать frontend и наоборот
- При изменении конфигурации — не трогать бизнес-логику
