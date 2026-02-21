# PriceRadar — План фазы MVP

## Сводка изменений после Discovery

На основании 15 интервью, MVP скорректирован:

| Было (до Discovery) | Стало (после Discovery) |
|---------------------|------------------------|
| Парсинг 3–5 источников, один маркетплейс на выбор | Ozon + Wildberries обязательно с первого дня |
| Мониторинг акций — фаза 2 | Базовый детект промо-лейблов — уже в MVP |
| Ручное добавление товаров | Ручное + импорт CSV/Excel |
| Еженедельный ИИ-дайджест | Еженедельный + опциональный ежедневный |
| Email-алерты | Email + Telegram-бот |
| Нет пробного периода | 14 дней бесплатно |
| Английский интерфейс | Русский UI с первого дня |

---

## 1. Структура проекта

```
imperecta/
├── backend/                     # Python FastAPI
│   ├── app/
│   │   ├── main.py              # FastAPI entrypoint
│   │   ├── config.py            # Settings (env vars)
│   │   ├── database.py          # SQLAlchemy engine, session
│   │   ├── models/              # SQLAlchemy models
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── product.py
│   │   │   ├── competitor.py
│   │   │   ├── price_snapshot.py
│   │   │   ├── alert.py
│   │   │   └── digest.py
│   │   ├── schemas/             # Pydantic schemas
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── product.py
│   │   │   ├── competitor.py
│   │   │   ├── alert.py
│   │   │   └── digest.py
│   │   ├── api/                 # Route handlers
│   │   │   ├── __init__.py
│   │   │   ├── deps.py          # Dependencies (auth, db session)
│   │   │   ├── auth.py
│   │   │   ├── products.py
│   │   │   ├── competitors.py
│   │   │   ├── analytics.py
│   │   │   ├── alerts.py
│   │   │   ├── digests.py
│   │   │   └── import_export.py
│   │   ├── services/            # Business logic
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py
│   │   │   ├── price_service.py
│   │   │   ├── alert_service.py
│   │   │   ├── digest_service.py
│   │   │   ├── ai_service.py   # Claude/OpenAI integration
│   │   │   └── import_service.py
│   │   ├── scrapers/            # Scraping engine
│   │   │   ├── __init__.py
│   │   │   ├── base.py          # Abstract base scraper
│   │   │   ├── ozon.py
│   │   │   ├── wildberries.py
│   │   │   ├── generic_web.py   # Universal URL scraper
│   │   │   └── proxy_manager.py
│   │   ├── workers/             # Celery tasks
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py
│   │   │   ├── scrape_tasks.py
│   │   │   ├── alert_tasks.py
│   │   │   ├── digest_tasks.py
│   │   │   └── scheduler.py     # Celery Beat config
│   │   └── notifications/       # Alert delivery
│   │       ├── __init__.py
│   │       ├── email_sender.py
│   │       └── telegram_bot.py
│   ├── alembic/                 # DB migrations
│   │   ├── env.py
│   │   └── versions/
│   ├── alembic.ini
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/                    # Vite + React
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── routes.tsx
│   │   ├── api/                 # API client
│   │   │   ├── client.ts        # Axios instance
│   │   │   ├── auth.ts
│   │   │   ├── products.ts
│   │   │   ├── competitors.ts
│   │   │   ├── analytics.ts
│   │   │   ├── alerts.ts
│   │   │   └── digests.ts
│   │   ├── hooks/               # React Query hooks
│   │   │   ├── useAuth.ts
│   │   │   ├── useProducts.ts
│   │   │   ├── useCompetitors.ts
│   │   │   ├── useAnalytics.ts
│   │   │   └── useAlerts.ts
│   │   ├── components/          # Shared UI
│   │   │   ├── ui/              # shadcn/ui components
│   │   │   ├── layout/
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   ├── Header.tsx
│   │   │   │   └── DashboardLayout.tsx
│   │   │   ├── charts/
│   │   │   │   ├── PriceChart.tsx
│   │   │   │   ├── ComparisonChart.tsx
│   │   │   │   └── TrendBadge.tsx
│   │   │   └── tables/
│   │   │       ├── ProductsTable.tsx
│   │   │       └── CompetitorPricesTable.tsx
│   │   ├── pages/
│   │   │   ├── LoginPage.tsx
│   │   │   ├── RegisterPage.tsx
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── ProductsPage.tsx
│   │   │   ├── ProductDetailPage.tsx
│   │   │   ├── CompetitorsPage.tsx
│   │   │   ├── AlertsPage.tsx
│   │   │   ├── DigestsPage.tsx
│   │   │   ├── ImportPage.tsx
│   │   │   └── SettingsPage.tsx
│   │   ├── stores/              # Zustand (light state)
│   │   │   └── authStore.ts
│   │   ├── lib/
│   │   │   └── utils.ts
│   │   └── i18n/                # Локализация
│   │       ├── ru.json
│   │       └── en.json
│   ├── index.html
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── package.json
├── docker-compose.yml           # Dev environment
├── docker-compose.prod.yml
├── .github/
│   └── workflows/
│       └── ci.yml
└── README.md
```

---

## 2. Понедельный план разработки (10 недель)

### Неделя 1–2: Фундамент

**Backend:**
- Инициализация FastAPI проекта, конфигурация
- SQLAlchemy модели + Alembic миграции
- Auth: регистрация, логин, JWT, refresh tokens
- CRUD: products, competitors, competitor_products
- Импорт товаров из CSV/Excel (pandas + openpyxl)

**Frontend:**
- Инициализация Vite + React + TypeScript + Tailwind + shadcn/ui
- Роутинг (React Router 7)
- Auth страницы (логин, регистрация)
- DashboardLayout (sidebar, header)
- CRUD страницы: Products, Competitors (таблицы, формы)

**Infra:**
- docker-compose: PostgreSQL + Redis + FastAPI + Celery
- GitHub repo + CI (lint, tests)

---

### Неделя 3–4: Scraping Engine

**Backend:**
- Базовый абстрактный класс scraper (base.py)
- Ozon scraper (Playwright): цена, наличие, promo-label
- Wildberries scraper (Playwright): цена, наличие, promo-label
- Generic web scraper: парсинг цен по CSS-селекторам (для кастомных сайтов)
- Proxy manager: ротация, retry, error handling
- Celery tasks: scheduled scraping (Celery Beat)
- Сохранение price_snapshots в БД

**Frontend:**
- Страница добавления конкурентного товара (URL + привязка к своему товару)
- Индикатор статуса парсинга (pending, success, error)
- Страница импорта CSV/Excel с preview

---

### Неделя 5–6: Дашборд и аналитика

**Backend:**
- Эндпоинты аналитики: история цен, дельты, мин/макс/среднее
- Расчёт трендов (рост/падение/стабильность)
- Детекция аномалий (>15% изменение за сутки)
- Агрегация данных по периодам (день, неделя, месяц)

**Frontend:**
- DashboardPage: сводка (количество товаров, алертов, последний парсинг)
- PriceChart: график цен (Recharts) — свой товар vs конкуренты
- ComparisonChart: bar chart сравнения текущих цен
- ProductDetailPage: полная история цены, все конкуренты
- TrendBadge: визуальный индикатор тренда (↑↓→)
- Промо-лейблы в таблице конкурентов (теги «акция», «скидка -30%»)

---

### Неделя 7–8: Алерты + Telegram-бот + ИИ-дайджест

**Backend:**
- Alert CRUD: создание правил (порог %, тип, канал)
- Alert engine: проверка после каждого scrape
- Дебаунсинг: не более 1 алерта на товар в час
- Email sender (SendGrid или Resend)
- Telegram bot: регистрация через /start + код привязки
- Telegram alerts: отправка уведомлений
- AI Digest service: Claude API → генерация еженедельной сводки на русском
- Celery tasks: weekly digest (пятница вечер), optional daily digest

**Frontend:**
- AlertsPage: список правил, создание/редактирование
- Настройки Telegram: инструкция + код привязки
- DigestsPage: список дайджестов, просмотр в markdown
- Настройки email/Telegram канала в профиле

---

### Неделя 9: Полировка + тестирование

- E2E сценарий: регистрация → добавление товаров → парсинг → дашборд → алерт
- Обработка ошибок: scraper failures, rate limits, пустые ответы
- Responsive UI (мобильная адаптация дашборда)
- Русская локализация UI (i18n)
- 14-дневный trial flow (ограничение после истечения)
- Loading/empty/error states на всех страницах
- Performance: пагинация таблиц, lazy loading графиков

---

### Неделя 10: Деплой + Closed Beta

- Деплой: Railway (backend + workers) + Cloudflare Pages (frontend)
- Supabase PostgreSQL (production)
- Upstash Redis (managed)
- Sentry (error tracking)
- Домен + SSL
- Landing page (простая, на Vite + shadcn)
- Инвайт 15 респондентов из Discovery
- Feedback form (Tally или Google Forms)
- Мониторинг: Sentry alerts, Uptime Robot

---

## 3. Схема БД (полная для MVP)

```sql
-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(100),
    company_name VARCHAR(200),
    plan VARCHAR(20) DEFAULT 'trial',         -- trial, starter, business, pro
    trial_ends_at TIMESTAMPTZ,
    telegram_chat_id BIGINT,
    telegram_link_code VARCHAR(20),
    language VARCHAR(5) DEFAULT 'ru',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Products (user's own products)
CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(500) NOT NULL,
    sku VARCHAR(100),
    current_price DECIMAL(12,2),
    currency VARCHAR(3) DEFAULT 'RUB',
    url TEXT,
    category VARCHAR(200),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_products_user ON products(user_id);

-- Competitors
CREATE TABLE competitors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    website_url TEXT,
    marketplace VARCHAR(50),                   -- ozon, wildberries, kaspi, custom
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_competitors_user ON competitors(user_id);

-- Competitor Products (linked to user's product)
CREATE TABLE competitor_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    competitor_id UUID REFERENCES competitors(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    name VARCHAR(500),
    last_price DECIMAL(12,2),
    last_promo_label VARCHAR(200),            -- "Скидка 30%", "Акция", etc.
    last_in_stock BOOLEAN,
    last_checked_at TIMESTAMPTZ,
    scraper_type VARCHAR(20) DEFAULT 'auto',  -- ozon, wildberries, generic
    css_selector_price VARCHAR(500),           -- for generic scraper
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_comp_products_product ON competitor_products(product_id);

-- Price Snapshots (historical data)
CREATE TABLE price_snapshots (
    id BIGSERIAL PRIMARY KEY,
    competitor_product_id UUID REFERENCES competitor_products(id) ON DELETE CASCADE,
    price DECIMAL(12,2),
    old_price DECIMAL(12,2),                  -- strikethrough price if present
    promo_label VARCHAR(200),
    in_stock BOOLEAN DEFAULT true,
    scraped_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_snapshots_comp_product ON price_snapshots(competitor_product_id);
CREATE INDEX idx_snapshots_scraped_at ON price_snapshots(scraped_at);

-- Alerts
CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    product_id UUID REFERENCES products(id) ON DELETE SET NULL,
    type VARCHAR(30) NOT NULL,                -- price_drop, price_increase, out_of_stock, new_promo
    threshold_percent DECIMAL(5,2),           -- e.g. 5.00 = 5%
    channel VARCHAR(20) DEFAULT 'email',      -- email, telegram, both
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Alert Events (log of sent alerts)
CREATE TABLE alert_events (
    id BIGSERIAL PRIMARY KEY,
    alert_id UUID REFERENCES alerts(id) ON DELETE CASCADE,
    competitor_product_id UUID REFERENCES competitor_products(id),
    old_price DECIMAL(12,2),
    new_price DECIMAL(12,2),
    message TEXT,
    sent_via VARCHAR(20),
    triggered_at TIMESTAMPTZ DEFAULT now()
);

-- Digests
CREATE TABLE digests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    period_type VARCHAR(10) NOT NULL,         -- daily, weekly
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    content_md TEXT,                           -- markdown content from AI
    summary_json JSONB,                       -- structured data for frontend
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_digests_user ON digests(user_id);
```

---

## 4. Промпты для Cursor IDE

Ниже — готовые промпты для Cursor, разбитые по этапам. Каждый промпт самодостаточен и предполагает, что предыдущий этап выполнен.

---

### Промпт 1: Инициализация Backend

```
Создай FastAPI backend проект для SaaS-платформы мониторинга цен конкурентов "PriceRadar".

Структура: app/main.py, app/config.py, app/database.py, app/models/, app/schemas/, app/api/, app/services/.

Требования:
- FastAPI с CORS middleware (разрешить localhost:5173 для dev)
- SQLAlchemy 2.0 async (asyncpg) + Alembic для миграций
- Pydantic Settings для конфигурации (.env файл)
- Роутеры подключаются через app/api/__init__.py

config.py:
- DATABASE_URL, REDIS_URL, JWT_SECRET, JWT_ALGORITHM="HS256", JWT_EXPIRATION_MINUTES=30
- CLAUDE_API_KEY, SENDGRID_API_KEY, TELEGRAM_BOT_TOKEN
- PROXY_LIST (comma-separated)

database.py:
- Async engine, async sessionmaker, Base (declarative_base)
- get_db dependency для роутеров

main.py:
- Lifespan: create tables on startup
- Include routers: auth, products, competitors, analytics, alerts, digests, import_export
- Health check endpoint /api/health

Создай requirements.txt: fastapi, uvicorn[standard], sqlalchemy[asyncio], asyncpg,
alembic, pydantic-settings, python-jose[cryptography], passlib[bcrypt], httpx, redis,
celery, python-telegram-bot, anthropic, sendgrid, openpyxl, pandas, playwright, beautifulsoup4, lxml.

Создай .env.example со всеми переменными.
Создай Dockerfile (python:3.12-slim).
Все комментарии в коде на английском. Имена переменных, функций, классов — только на английском.
```

---

### Промпт 2: SQLAlchemy модели

```
Создай SQLAlchemy 2.0 async модели для PriceRadar в app/models/.

Модели (каждая в отдельном файле):

1. User: id (UUID, PK), email (unique), password_hash, name, company_name, 
   plan (enum: trial/starter/business/pro, default trial), trial_ends_at,
   telegram_chat_id (BigInteger nullable), telegram_link_code (String(20) nullable),
   language (default "ru"), created_at, updated_at.

2. Product: id (UUID), user_id (FK users, CASCADE), name (String 500), sku (String 100 nullable),
   current_price (Numeric 12,2), currency (default "RUB"), url (Text nullable),
   category (String 200 nullable), is_active (default true), created_at, updated_at.
   Index on user_id.

3. Competitor: id (UUID), user_id (FK users, CASCADE), name (String 200),
   website_url (Text nullable), marketplace (String 50: ozon/wildberries/kaspi/custom),
   notes (Text nullable), created_at. Index on user_id.

4. CompetitorProduct: id (UUID), product_id (FK products, CASCADE),
   competitor_id (FK competitors, CASCADE), url (Text NOT NULL), name (String 500 nullable),
   last_price (Numeric 12,2), last_promo_label (String 200 nullable),
   last_in_stock (Boolean), last_checked_at (DateTime nullable),
   scraper_type (String 20, default "auto"), css_selector_price (String 500 nullable),
   is_active (default true), created_at. Index on product_id.

5. PriceSnapshot: id (BigInteger, autoincrement PK), competitor_product_id (FK, CASCADE),
   price (Numeric 12,2), old_price (Numeric 12,2 nullable), promo_label (String 200 nullable),
   in_stock (default true), scraped_at (default now). Indexes on competitor_product_id и scraped_at.

6. Alert: id (UUID), user_id (FK CASCADE), product_id (FK SET NULL nullable),
   type (String 30: price_drop/price_increase/out_of_stock/new_promo),
   threshold_percent (Numeric 5,2 nullable), channel (String 20: email/telegram/both, default email),
   is_active (default true), created_at.

7. AlertEvent: id (BigInteger), alert_id (FK CASCADE), competitor_product_id (FK nullable),
   old_price, new_price, message (Text), sent_via (String 20), triggered_at (default now).

8. Digest: id (UUID), user_id (FK CASCADE), period_type (String 10: daily/weekly),
   period_start, period_end, content_md (Text), summary_json (JSON nullable),
   sent_at (DateTime nullable), created_at.

app/models/__init__.py — импортировать все модели.
Использовать mapped_column, Mapped, relationship где нужно.
UUID генерировать через uuid4. Timestamps через func.now().
Все комментарии и нейминг — на английском.
```

---

### Промпт 3: Auth (регистрация, логин, JWT)

```
Реализуй полную систему аутентификации для PriceRadar.

app/services/auth_service.py:
- hash_password(password) -> str (bcrypt через passlib)
- verify_password(plain, hashed) -> bool
- create_access_token(user_id: UUID, expires_delta: timedelta) -> str (jose JWT)
- create_refresh_token(user_id: UUID) -> str (срок 7 дней)
- decode_token(token: str) -> dict

app/api/deps.py:
- get_current_user dependency: извлекает JWT из Authorization: Bearer header,
  декодирует, возвращает User из БД. Если невалиден — 401.

app/schemas/user.py:
- UserRegister: email, password (min 8), name, company_name (optional)
- UserLogin: email, password
- UserResponse: id, email, name, company_name, plan, trial_ends_at, language, created_at
- TokenResponse: access_token, refresh_token, token_type

app/api/auth.py — роутер prefix="/api/auth":
- POST /register: создать пользователя, plan="trial", trial_ends_at=now+14 days, вернуть tokens
- POST /login: проверить credentials, вернуть tokens
- POST /refresh: по refresh_token вернуть новый access_token
- GET /me: вернуть текущего пользователя (protected)

Валидация: дупликат email → 409, неверный пароль → 401.
Все комментарии и нейминг — на английском.
```

---

### Промпт 4: CRUD Products + Competitors + Import

```
Реализуй CRUD для товаров и конкурентов в PriceRadar. Все эндпоинты protected (require get_current_user).

app/schemas/product.py:
- ProductCreate: name, sku?, current_price, currency?, url?, category?
- ProductUpdate: все optional
- ProductResponse: все поля + competitor_count (кол-во привязанных конкурентных товаров)
- ProductListResponse: items list + total count

app/api/products.py — prefix="/api/products":
- GET / — список товаров текущего пользователя. Query params: search, category, page, limit. 
  Включить competitor_count через subquery.
- GET /{id} — детали товара + список competitor_products с last_price
- POST / — создать товар
- PUT /{id} — обновить
- DELETE /{id} — удалить (каскадно)

app/schemas/competitor.py:
- CompetitorCreate: name, website_url?, marketplace (enum), notes?
- CompetitorProductCreate: product_id, competitor_id, url, name?, scraper_type?, css_selector_price?
- CompetitorProductResponse: все поля + price_diff (разница с товаром пользователя в %)

app/api/competitors.py — prefix="/api/competitors":
- GET / — список конкурентов пользователя
- POST / — создать конкурента
- PUT /{id}, DELETE /{id}
- POST /products — добавить конкурентный товар (привязать URL к product + competitor)
- GET /products/{product_id} — все конкурентные товары для данного product
- DELETE /products/{id} — удалить привязку

app/api/import_export.py — prefix="/api/import":
- POST /products/csv — загрузить CSV/Excel файл (UploadFile).
  Парсинг через pandas. Колонки: name, sku, price, url, category.
  Возврат: { imported: N, errors: [{row: N, message: "..."}] }
- GET /products/template — скачать CSV-шаблон

Все комментарии и нейминг — на английском.
```

---

### Промпт 5: Scraper Engine

```
Реализуй модуль парсинга цен для PriceRadar.

app/scrapers/base.py:
- AbstractScraper (ABC):
  - async scrape(url: str) -> ScrapedData (dataclass: price, old_price, promo_label, in_stock, product_name)
  - handle retries (3 attempts, exponential backoff)
  - random delay между запросами (1-3 сек)

app/scrapers/proxy_manager.py:
- ProxyManager: загружает список прокси из config.PROXY_LIST
  - get_proxy() -> str (round-robin ротация)
  - mark_failed(proxy) — временно исключить на 5 минут
  - Если прокси нет — работать напрямую (для dev)

app/scrapers/ozon.py — OzonScraper(AbstractScraper):
- Использует Playwright (async) с headless Chromium
- Навигация на URL товара Ozon
- Извлечение: текущая цена (data-widget-name="webPrice" или CSS-селекторы), 
  старая цена (перечёркнутая), наличие ("Нет в наличии"), промо-лейбл ("Скидка", "Акция")
- User-Agent ротация, прокси из ProxyManager
- Обработка ошибок: timeout, blocked, page not found

app/scrapers/wildberries.py — WildberriesScraper(AbstractScraper):
- Использует API Wildberries (basket URLs + card detail API, не Playwright):
  https://card.wb.ru/cards/v2/detail?appType=1&curr=rub&dest=-1257786&nm={article_id}
- Извлечение article_id из URL
- price = salePriceU / 100, old_price = priceU / 100
- in_stock по наличию sizes.stocks
- promo_label из sale field

app/scrapers/generic_web.py — GenericWebScraper(AbstractScraper):
- Использует httpx + BeautifulSoup
- Принимает css_selector_price из CompetitorProduct
- Если селектор не задан — попытка автоопределения через common patterns:
  [itemprop="price"], .price, .product-price, [data-price]
- Fallback: Playwright если httpx не получил данные

app/services/price_service.py:
- async scrape_competitor_product(competitor_product_id: UUID):
  - Определить scraper_type (ozon/wildberries/generic) по URL или полю
  - Вызвать соответствующий scraper
  - Сохранить PriceSnapshot
  - Обновить last_price, last_promo_label, last_in_stock, last_checked_at в CompetitorProduct
  - Вернуть ScrapedData

Автоопределение scraper_type по URL:
- "ozon.ru" → ozon
- "wildberries.ru" или "wb.ru" → wildberries
- всё остальное → generic

Все комментарии и нейминг — на английском.
```

---

### Промпт 6: Celery Workers + Scheduler

```
Реализуй Celery workers и планировщик для PriceRadar.

app/workers/celery_app.py:
- Celery app с Redis broker (config.REDIS_URL)
- Result backend: Redis
- Task serializer: json

app/workers/scrape_tasks.py:
- Task scrape_single(competitor_product_id: str):
  - Вызывает price_service.scrape_competitor_product
  - При ошибке — retry 3 раза с exponential backoff
  - Логирование результата

- Task scrape_user_products(user_id: str):
  - Получить все active competitor_products пользователя
  - Для каждого — вызвать scrape_single.delay() с задержкой (stagger по 2-5 сек)

- Task scrape_all():
  - Получить всех active пользователей
  - Для каждого — scrape_user_products.delay()

app/workers/alert_tasks.py:
- Task check_alerts(competitor_product_id: str, old_price, new_price, promo_label):
  - Вызывается после успешного scrape
  - Проверить все активные alerts для product, связанного с этим competitor_product
  - Если порог превышен — создать AlertEvent, отправить уведомление
  - Дебаунс: не отправлять если AlertEvent для этого alert+competitor_product был < 1 часа назад

app/workers/digest_tasks.py:
- Task generate_weekly_digest(user_id: str):
  - Собрать данные за неделю: топ изменений цен, новые акции, out-of-stock
  - Передать в ai_service.generate_digest() — вернёт markdown на русском
  - Сохранить Digest в БД
  - Отправить по email и/или Telegram

- Task generate_daily_digest(user_id: str):
  - Аналогично, но за день. Только для пользователей с plan != "starter"

app/workers/scheduler.py (Celery Beat config):
- scrape_all: каждые 6 часов (crontab)
- generate_weekly_digest для всех пользователей: пятница 18:00 UTC
- generate_daily_digest для pro-пользователей: ежедневно 08:00 UTC
- cleanup_old_snapshots: раз в неделю (удалять snapshots старше 90 дней)

Все комментарии и нейминг — на английском.
```

---

### Промпт 7: Аналитика (API эндпоинты)

```
Реализуй эндпоинты аналитики для PriceRadar.

app/api/analytics.py — prefix="/api/analytics", все protected.

GET /products/{product_id}/price-history:
- Query params: period (7d, 30d, 90d), competitor_product_id (optional, all if not set)
- Возврат: { product_name, my_price, competitors: [{ competitor_name, competitor_product_id,
  data_points: [{ date, price, promo_label, in_stock }] }] }
- Группировка: если period=7d — каждая точка, 30d — по дням (avg), 90d — по неделям (avg)

GET /products/{product_id}/comparison:
- Текущее сравнение: мой price vs все конкуренты
- Возврат: { my_price, competitors: [{ name, price, diff_amount, diff_percent,
  promo_label, in_stock, trend (up/down/stable) }] }
- trend: сравнить текущую цену с ценой 7 дней назад

GET /dashboard/summary:
- Сводка для дашборда текущего пользователя:
  - total_products, total_competitors, total_tracked_items
  - last_scrape_at (время последнего парсинга)
  - alerts_triggered_today
  - price_changes_today: { drops: N, increases: N }
  - top_changes: [{ product_name, competitor_name, old_price, new_price, change_percent }] (топ-5)
  - active_promos: [{ competitor_name, product_name, promo_label }] (текущие акции конкурентов)

GET /dashboard/anomalies:
- Аномалии за последние 24 часа (изменение > 15%):
  - [{ product_name, competitor_name, old_price, new_price, change_percent, detected_at }]

Все расчёты через SQL-запросы (не загружать всё в память).
Все комментарии и нейминг — на английском.
```

---

### Промпт 8: ИИ-дайджест + Telegram

```
Реализуй AI-дайджест и Telegram-бот для PriceRadar.

app/services/ai_service.py:
- async generate_digest(user_id, period_data: dict) -> str:
  - Использует Anthropic Claude API (anthropic python SDK)
  - System prompt: "Ты — аналитик конкурентной разведки. Пиши на русском языке.
    Генерируй краткий, полезный дайджест изменений цен для e-commerce бизнеса.
    Формат: markdown. Структура: Ключевые изменения, Акции конкурентов,
    Рекомендации по ценообразованию, Аномалии (если есть)."
  - User prompt: JSON с данными за период (top_changes, promos, anomalies, summary stats)
  - Вернуть markdown строку
  - Error handling: timeout, API errors → fallback шаблонный дайджест без AI

app/notifications/telegram_bot.py:
- Telegram bot (python-telegram-bot, async):
  - /start — приветствие, инструкция: "Введите код привязки из личного кабинета PriceRadar"
  - Обработка текстового сообщения: проверить telegram_link_code в БД users
    → если найден, сохранить chat_id, сбросить код, ответить "Аккаунт привязан!"
  - /status — показать кол-во отслеживаемых товаров и последнюю цену
  - /digest — получить последний дайджест

- async send_telegram_alert(chat_id: int, message: str):
  - Отправить форматированное сообщение (HTML parse_mode)
  - Retry 2 раза при ошибке

- async send_telegram_digest(chat_id: int, digest_md: str):
  - Конвертировать markdown в Telegram HTML (bold, italic)
  - Если длинный — разбить на части по 4096 символов

app/notifications/email_sender.py:
- async send_alert_email(to: str, subject: str, body_html: str):
  - Через SendGrid API
  - Простой HTML шаблон: лого, заголовок, тело, footer

- async send_digest_email(to: str, digest_md: str):
  - Конвертировать markdown в HTML
  - Обернуть в email-шаблон

app/api/auth.py — добавить эндпоинт:
- POST /api/auth/telegram-link — генерирует 6-значный код, сохраняет в user.telegram_link_code,
  возвращает { code: "XXXXXX", bot_url: "https://t.me/PriceRadarBot" }

Все комментарии и нейминг — на английском.
```

---

### Промпт 9: Инициализация Frontend

```
Создай frontend для PriceRadar: Vite 6 + React 19 + TypeScript + React Router 7 + Tailwind CSS 4 + shadcn/ui.

Инициализация:
- vite.config.ts: proxy /api → http://localhost:8000 (dev)
- tailwind.config.ts: настроить shadcn/ui
- Установить shadcn/ui компоненты: button, input, card, table, badge, dialog, dropdown-menu,
  select, tabs, toast, separator, avatar, skeleton, sheet
- Установить: @tanstack/react-query, axios, recharts, lucide-react, zustand, react-i18next, date-fns

src/api/client.ts:
- Axios instance, baseURL="/api", interceptor: добавлять JWT из localStorage,
  на 401 — redirect на /login

src/stores/authStore.ts (Zustand):
- user, tokens, login(), logout(), setUser()

src/routes.tsx (React Router 7):
- / → redirect to /dashboard
- /login, /register — публичные
- /dashboard, /products, /products/:id, /competitors, /alerts, /digests, /import, /settings — protected (проверка auth)

src/components/layout/DashboardLayout.tsx:
- Sidebar слева (сворачиваемый): навигация с иконками (lucide-react):
  Dashboard, Товары, Конкуренты, Алерты, Дайджесты, Импорт, Настройки
- Header: имя компании, аватар, dropdown (профиль, выход)
- Main content area с padding
- Русский язык по умолчанию (i18n)
- Mobile: sidebar как Sheet (shadcn)

Страницы-заглушки для всех роутов (с заголовком и "Coming soon").
LoginPage и RegisterPage — полностью рабочие формы (подключены к /api/auth).

Дизайн: тёмная sidebar (#1a1a2e), белый content area, акцентный цвет #6366f1 (indigo).
Все комментарии и нейминг — на английском.
```

---

### Промпт 10: Frontend — Dashboard + Products

```
Реализуй DashboardPage и ProductsPage для PriceRadar.

src/hooks/useAnalytics.ts:
- useDashboardSummary() — GET /api/analytics/dashboard/summary (TanStack Query)
- usePriceHistory(productId, period) — GET /api/analytics/products/{id}/price-history
- useComparison(productId) — GET /api/analytics/products/{id}/comparison

src/pages/DashboardPage.tsx:
- 4 stat-карточки сверху (shadcn Card): Товаров, Конкурентов, Алертов сегодня, Изменений цен
- Секция "Топ-5 изменений" — таблица: товар, конкурент, было, стало, % изменения.
  Цвет: зелёный если снижение (хорошо для нас), красный если рост конкурента.
- Секция "Активные акции конкурентов" — badges с promo_label
- Skeleton loading states для всех секций

src/pages/ProductsPage.tsx:
- Поиск + фильтр по категории
- Таблица (shadcn Table): Название, SKU, Моя цена, Мин. цена конкурентов,
  Макс. цена, Кол-во конкурентов, Последний парсинг
- Цветовая индикация: если моя цена > мин. конкурента → красный badge
- Кнопки: Добавить товар (dialog), Импорт CSV
- Пагинация

src/pages/ProductDetailPage.tsx:
- Заголовок: название, SKU, моя цена
- Табы: "График цен", "Конкуренты", "Алерты"
- Таб "График цен": PriceChart (Recharts LineChart) — мой товар + все конкуренты.
  Переключатель периода: 7д / 30д / 90д. Tooltip с ценой и датой.
- Таб "Конкуренты": таблица competitor_products с last_price, diff%, promo_label, in_stock, trend badge
- Таб "Алерты": список алертов для этого товара + кнопка "Создать алерт"

src/components/charts/PriceChart.tsx:
- Recharts LineChart, responsive
- Линия для каждого конкурента + пунктирная линия "моя цена"
- Легенда, tooltip, grid
- Цвета: мой — indigo, конкуренты — автоматически из палитры

Все тексты на русском. Комментарии и нейминг — на английском.
```

---

### Промпт 11: Frontend — Competitors, Alerts, Digests, Import, Settings

```
Реализуй оставшиеся страницы PriceRadar.

src/pages/CompetitorsPage.tsx:
- Список конкурентов: имя, сайт, маркетплейс (badge: Ozon/WB/Custom), кол-во товаров
- Добавление конкурента: dialog с формой (name, url, marketplace select)
- Раскрытие: список привязанных competitor_products с ценами
- Добавление конкурентного товара: dialog (выбор product из select, URL, scraper_type auto-detect)

src/pages/AlertsPage.tsx:
- Список активных правил: тип (badge), товар, порог, канал, toggle вкл/выкл
- Создание алерта: dialog — выбор товара, тип (price_drop/price_increase/out_of_stock/new_promo),
  порог %, канал (email/telegram/both)
- История срабатываний (последние 20): дата, товар, конкурент, было→стало, отправлено через

src/pages/DigestsPage.tsx:
- Список дайджестов (карточки): тип (daily/weekly), период, дата создания
- Клик — раскрытие markdown контента (отрендерить через dangerouslySetInnerHTML или react-markdown)
- Badge "Отправлен" / "Черновик"

src/pages/ImportPage.tsx:
- Drag-and-drop зона для CSV/Excel (или кнопка выбора файла)
- Preview: таблица первых 5 строк из файла
- Кнопка "Импортировать"
- Результат: "Импортировано: N, Ошибки: M" с деталями ошибок
- Ссылка на скачивание шаблона

src/pages/SettingsPage.tsx:
- Секция "Профиль": имя, компания, email (readonly), язык
- Секция "Telegram": статус привязки, кнопка "Получить код привязки" → показать код + QR/ссылку на бота
- Секция "Уведомления": предпочтительный канал, время дайджеста
- Секция "Тариф": текущий план, дата окончания trial, кнопка "Upgrade" (заглушка)

Все тексты на русском. Комментарии и нейминг — на английском.
```

---

### Промпт 12: Docker Compose + CI

```
Создай docker-compose.yml для локальной разработки PriceRadar и CI pipeline.

docker-compose.yml:
- postgres:16 — порт 5432, volume для данных, POSTGRES_DB=priceradar
- redis:7-alpine — порт 6379
- backend (Dockerfile) — порт 8000, зависит от postgres и redis,
  command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
  volumes: ./backend/app:/app/app (hot reload)
- celery-worker — тот же Dockerfile, command: celery -A app.workers.celery_app worker -l info
- celery-beat — command: celery -A app.workers.celery_app beat -l info
- frontend — node:20-alpine, порт 5173, command: npm run dev -- --host,
  volumes: ./frontend:/app (hot reload)

.env файл для docker-compose с дефолтами.

docker-compose.prod.yml:
- Без hot reload, без volumes
- Backend: gunicorn с uvicorn workers
- Frontend: nginx serving built static files
- Healthchecks для всех сервисов

.github/workflows/ci.yml:
- Trigger: push to main, PR to main
- Jobs:
  - backend-lint: ruff check
  - backend-test: pytest с test DB (postgres service container)
  - frontend-lint: eslint
  - frontend-build: npm run build

Все комментарии на английском.
```

---

## 5. Критерии готовности MVP

Перед запуском closed beta проверить:

- [ ] Регистрация → подтверждение email → логин работает
- [ ] Добавление товаров вручную и через CSV/Excel
- [ ] Добавление конкурентов и привязка URL
- [ ] Парсинг Ozon — цена, старая цена, промо, наличие
- [ ] Парсинг Wildberries — цена, старая цена, промо, наличие  
- [ ] Парсинг произвольного сайта по CSS-селектору
- [ ] Автоматический парсинг по расписанию (каждые 6 часов)
- [ ] Дашборд: статистика, топ изменений, акции
- [ ] График цен: 7д / 30д / 90д
- [ ] Алерты: создание правил, срабатывание, email доставка
- [ ] Telegram-бот: привязка, алерты, /digest команда
- [ ] ИИ-дайджест: еженедельная генерация на русском
- [ ] 14-дневный trial работает корректно
- [ ] UI полностью на русском языке
- [ ] Мобильная адаптация (sidebar collapsible)
- [ ] Sentry подключён, ошибки логируются
- [ ] Production деплой стабилен 24 часа без падений
