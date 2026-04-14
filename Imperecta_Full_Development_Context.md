# Imperecta — Полный контекст разработки для AI-агента

**Дата:** 2026-04-04
**Язык общения:** русский
**Код:** комментарии, переменные, функции — только английский

---

## 1. Что такое Imperecta

SaaS-платформа конкурентной разведки и рыночной аналитики для e-commerce.

**Ключевые функции:**
- Отслеживание цен конкурентов на маркетплейсах (автоматический парсинг)
- Рыночные виджеты: forex, крипто, сырьё, топливо
- AI-дайджесты и алерты при изменениях цен
- Встроенный AI-аналитик (Claude API)
- Экспорт данных в PowerBI/Tableau/Excel

**Целевая аудитория:** малый и средний e-commerce бизнес в Европе и странах СНГ (бывшего СССР).

**География:** 44 страны — вся Европа + все страны бывшего СССР.

---

## 2. Технический стек

### Backend
- Python 3.12 + FastAPI
- SQLAlchemy 2.0 async (asyncpg) + Alembic
- Celery + Redis (Upstash) — фоновые задачи
- Decodo Web Scraping API → httpx → Playwright (failover)
- Anthropic Claude API — AI-функции
- Resend — email, python-telegram-bot — Telegram

### Frontend
- Vite 6 + React 19 + TypeScript
- Tailwind CSS 4 + shadcn/ui (Radix)
- TanStack Query v5, Zustand v5
- react-i18next (en, ru, ar, zh, es, fr, uk, ro)
- Темы: светлая + тёмная (по умолчанию тёмная)

### Инфраструктура
- Railway: 3 сервиса (backend, celery-worker, celery-beat)
- Cloudflare Pages: frontend
- Supabase: PostgreSQL
- Upstash: Redis

---

## 3. Структура проекта

```
backend/app/
├── models/                    # ORM v2 (единый слой для Alembic)
│   ├── __init__.py            # Re-export ALL models
│   ├── core.py                # User, UserSubscription, UserProduct
│   ├── dimensions.py          # DimDate, DimCountry, DimCurrency, DimMarketplace,
│   │                          # DimCategory, DimBrand, DimProduct, DimSeller
│   ├── facts.py               # FactListing, FactPrice, FactReview, FactStock,
│   │                          # FactSearchTrend, FactCurrencyRate, FactTariff, FactPromo,
│   │                          # FactCryptoPrice, FactCommodityPrice, FactFuelPrice
│   └── app_tables.py          # Alert, AlertEvent, Digest, AIChatSession,
│                               # AIChatMessage, ScrapeJob, ScrapeLog, ApiLog, DataExport
├── modules/
│   ├── core/                  # auth, admin, telegram
│   ├── marketplaces/          # marketplace CRUD (dim_marketplace)
│   ├── scraper/               # discovery, scraping, tasks
│   │   ├── api.py             # Admin endpoints (trigger discovery/scrape)
│   │   ├── tasks.py           # Celery orchestration
│   │   ├── discovery.py       # DiscoveryCrawler + DiscoveryResult
│   │   ├── service.py         # GlobalScrapeService (DB persistence)
│   │   ├── scraper_pool.py    # ScraperPool + PoolScrapeResult (fetch+extract)
│   │   └── extractors.py      # Extraction toolkit (JSON-LD, meta, auto-detect)
│   ├── product_pool/          # Global pool API (/api/pool/*)
│   ├── market_data/           # Forex, crypto, commodities, fuel ingestion
│   ├── dashboard/             # KPI, overview
│   ├── user_products/         # User's tracked products
│   ├── analytics/             # Forecasts, benchmarks
│   ├── alerts/                # Alert rules and events
│   ├── digests/               # AI digest generation
│   └── ai_analyst/            # AI chat (Claude)
├── workers/
│   ├── celery_app.py
│   ├── scheduler.py           # Beat schedule (CURRENTLY EMPTY — disabled)
│   ├── cleanup_tasks.py
│   └── maintenance_tasks.py   # MV refresh, partition management
└── alembic/
    └── versions/
        ├── 001_v2_schema.py … 008_fix_alembic_version_length.py
        └── 009_full_v2_schema_rebuild.py  # HEAD — idempotent full v2 DDL
```

---

## 4. База данных — текущее состояние (PostgreSQL v2, Supabase)

### Схема: Star Schema

**31 таблица** (ORM / `public` base tables, без учёта партиций `fact_price_*`):
- 3 core: `users`, `user_subscriptions`, `user_products`
- 8 dim: `dim_date`, `dim_country`, `dim_currency`, `dim_marketplace`, `dim_category`, `dim_brand`, `dim_product`, `dim_seller`
- 11 fact: `fact_listing`, `fact_price` (partitioned), `fact_review`, `fact_stock`, `fact_search_trend`, `fact_currency_rate`, `fact_tariff`, `fact_promo`, `fact_crypto_price`, `fact_commodity_price`, `fact_fuel_price`
- 9 app: `alerts`, `alert_events`, `digests`, `ai_chat_sessions`, `ai_chat_messages`, `scrape_jobs`, `scrape_logs`, `api_logs`, `data_exports`
- 2 MV: `mv_daily_price_summary`, `mv_marketplace_health`

### Seeds (заполнены):
- `dim_date`: 2557 дней (2024-01-01 → 2030-12-31)
- `dim_currency`: 30 валют (EUR, USD, RUB, UAH, KZT, BYN, ...)
- `dim_country`: 44 страны (вся Европа + СНГ)

### Текущие данные (2026-03-31):
| Таблица | Строк | Комментарий |
|---------|-------|-------------|
| dim_marketplace | 5 | Тестовые маркетплейсы |
| dim_product | 72 | Discovery нашёл 72 URL товаров |
| fact_listing | 72 | Все 72 listings созданы |
| fact_price | **0** | ❌ Scraping не прошёл — нет цен |
| scrape_logs | **0** | ❌ Ни одной попытки scrape не записано |
| scrape_jobs | 5 | Discovery jobs (type='discovery') |
| users | 2 | Admin + trial user |

### Alembic миграции:
Цепочка: `001` → … → `008_fix_alembic_version_length` → **`009_full_v2_schema_rebuild` (head)**.

Версия хранится в `alembic_meta.alembic_version` (НЕ в `public`); колонка **`version_num`** — **VARCHAR(255)**. В **`alembic/env.py`** после **`run_sync(do_run_migrations)`** выполняется **`await connection.commit()`** (обязательно для сохранения DDL при async).

### CHECK constraints (критичные для маппинга):
- `scrape_logs.status`: включает в т.ч. `'missing_critical_data'`, `'technical_error'` (полный список — миграции **005**/**009** + ORM **`ScrapeLog`**)
- `dim_marketplace.scraper_type`: `'web_api','playwright','httpx','api_official','rss','feed'`
- `dim_marketplace.source_type`: `'marketplace','price_aggregator','direct_retail','classified','b2b_platform','brand_store'`
- `fact_price`: partitioned by `date_id` (YYYYMMDD integer)

---

## 5. Parser архитектура — каноничный runtime path

```
                    Admin UI / API
                         │
                         ▼
                  scraper/api.py          ← HTTP trigger
                         │
                         ▼
                  scraper/tasks.py        ← Celery orchestration
                    │            │
                    ▼            ▼
          discovery.py      service.py    ← Business logic
                    │            │
                    └──────┬─────┘
                           ▼
                    scraper_pool.py       ← Fetch + Extract facade (ЕДИНСТВЕННЫЙ)
                           │
                           ▼
                    extractors.py         ← JSON-LD → meta → custom → auto-detect → merge
```

### Fetch layer priority:
1. Decodo API (managed proxy, anti-bot)
2. httpx (direct)
3. Playwright (headless browser)

Если `requires_js=True` → Playwright поднимается выше httpx.

### Extraction layer priority:
1. JSON-LD (`extract_from_jsonld`)
2. meta tags (`extract_from_meta_tags`)
3. custom selectors (`extract_with_custom_selectors`)
4. auto-detect heuristics (`extract_auto_detect`)
5. merge (`merge_results`)

### Ключевые контракты:

**PoolScrapeResult** (scraper_pool.py):
```python
@dataclass
class PoolScrapeResult:
    success: bool
    url: str
    data: ExtractedProduct | None = None
    scraper_layer: str | None = None
    duration_ms: int | None = None
    error: str | None = None
    is_partial: bool = False
    is_empty: bool = False
    fields_extracted: list[str] = field(default_factory=list)
    fields_missing: list[str] = field(default_factory=list)
```

**DiscoveryResult** (discovery.py):
```python
@dataclass
class DiscoveryResult:
    marketplace_id: UUID
    status: str          # 'completed', 'partial', 'error', 'no_categories'
    started_at: datetime
    completed_at: datetime | None
    pages_scanned: int
    candidate_urls_found: int
    accepted_urls: int
    duplicate_urls: int
    rejected_urls: int
    persisted_listings: int
    job_id: UUID | None
    errors: list[str]
    discovery_method: str
```

### engine.py — УДАЛЁН
Был legacy dual-path (UniversalScraper, ScraperFactory, BaseScraper). Полностью удалён из production runtime. Все ссылки мигрированы на scraper_pool.

---

## 6. Persistence rules (текущие)

### Discovery → DB:
- Accepted URLs → `DimProduct` (placeholder name=URL) + `FactListing` (url_hash dedupe)
- Duplicate URLs → пропускаются (url_hash уникальный)
- Rejected URLs → не создают записей
- Discovery run → `ScrapeJob` (job_type='discovery')

### Scrape → DB:
- **FactPrice пишется ТОЛЬКО когда:**
  - price ≠ None, price > 0, price ≤ 9,999,999,999.99
  - currency ≠ None
- **FactPrice НЕ пишется когда:**
  - price missing, currency missing, fetch failed, overflow
- **FactListing обновляется:**
  - `last_checked_at` = всегда при любом attempt
  - `last_price`, `last_currency_code`, `last_in_stock` = из данных (nullable)
  - `consecutive_errors`: reset=0 при success, +1 при failure
  - `last_error`: null при success, error message при failure
- **Никаких фейковых дефолтов:**
  - НЕТ `"USD"` fallback для currency
  - НЕТ `in_stock = True` хардкода
  - НЕТ `price = 0` подстановки

### scrape_logs:
Записывается при каждом scrape attempt (success и failure).

---

## 7. Что было сделано в этом диалоге (хронология)

### Фаза 1: Создание структуры БД v2
1. Создана схема БД v2 (Star Schema) — 28 таблиц + 2 MV
2. Промпты 1-4 для Cursor: модели Core+Dimensions → Facts+App → импорты → миграция

### Фаза 2: Дополнение схемы
3. Найдены пропуски: нет таблиц crypto/commodities/fuel, нет полей discovery в dim_marketplace
4. Миграция 002: 3 новые fact таблицы + 12 колонок в dim_marketplace + url_hash + preferences

### Фаза 3: Перевод сервисного слоя на v2
5. Аудит: 13 сервисов, 6 schema файлов, 3 task файла ссылаются на удалённые таблицы
6. Промпты 1-5: schemas → read-сервисы → write-сервисы → tasks → cleanup

### Фаза 4: Борьба с Alembic миграциями (7+ итераций)
7. `alembic_meta schema does not exist` → CREATE SCHEMA IF NOT EXISTS
8. `cannot insert multiple commands` → asyncpg single-statement rule
9. `alembic_version already exists` → убрать дублирование в 001
10. `column plan does not exist` → `plan::text` при backup (ENUM → TEXT cast)
11. `scraper_type CHECK violation` → маппинг старых значений
12. `country_code FK violation` → убран restore маркетплейсов
13. `users.timezone does not exist` → миграция 003 + 004 + ручной SQL в Supabase
14. DROP SCHEMA не работает в Supabase → ручное удаление старых таблиц через SQL Editor

### Фаза 5: Ручная фиксация БД через Supabase SQL Editor
15. ALTER users: ENUM→VARCHAR, добавлены timezone/default_currency/preferences и др.
16. DROP 25+ старых таблиц (admin_marketplaces, global_products, markets_*, etc.)
17. Seeds: dim_date, dim_currency (с is_active=true), dim_country (с is_active=true)
18. Пересозданы app таблицы: alerts, alert_events, digests, ai_chat_*, api_logs, scrape_logs
19. Materialized views пересозданы

### Фаза 6: Parser stabilization
20. engine.py удалён из runtime, все импорты мигрированы на scraper_pool
21. Persistence: убраны фейковые дефолты (USD, in_stock=True), добавлен quality gate
22. Контракты: PoolScrapeResult расширен (is_partial, fields_extracted), DiscoveryResult dataclass
23. Marketplace CRUD оживлён (add-by-url, import, delete, quotas)

### Фаза 7: Тестирование (текущая стадия)
24. Discovery отработал: 5 маркетплейсов, 72 product URLs найдены
25. **Scraping НЕ запускался или упал**: fact_price=0, scrape_logs=0

---

## 8. ТЕКУЩИЙ БЛОКЕР — scraping не работает

### Симптомы:
- `fact_price` = 0 строк
- `scrape_logs` = 0 строк
- В UI товары показываются как числовые ID без названий и цен
- Discovery отработал (72 listings), но scrape ни разу не прошёл

### Что нужно сделать:
1. **Запустить scrape вручную** через `POST /api/admin/pool/trigger-scrape`
2. **Проверить логи Railway** — найти ошибку
3. **Диагностировать**: Decodo не настроен? httpx blocked? Playwright timeout? quality gate отклоняет?
4. Исправить и добиться чтобы хотя бы 1 товар получил цену

### Диагностические запросы:
```sql
-- Проверить listings
SELECT fl.id, fl.external_url, fl.last_checked_at, fl.consecutive_errors, fl.last_error,
       dm.name as marketplace, dm.domain
FROM fact_listing fl
JOIN dim_marketplace dm ON fl.marketplace_id = dm.id
LIMIT 10;

-- После trigger-scrape проверить
SELECT * FROM scrape_logs ORDER BY created_at DESC LIMIT 10;
SELECT * FROM fact_price LIMIT 10;
```

---

## 9. Правила проекта (обязательные)

1. **Масштабируемость**: магазинов, товаров, пользователей может быть бесконечно. Запрещено хардкодить.
2. **Без mock данных**: никогда, нигде.
3. **Без фейковых дефолтов**: нет `"USD"` fallback, нет `in_stock=True`, нет `price=0`.
4. **Темы**: светлая + тёмная, весь UI поддерживает обе.
5. **Мультиязычность**: языки ООН + румынский + украинский.
6. **Безопасность**: данные шифруются at rest с авторотирующимися ключами, выдаются по одному с логированием.
7. **Beat отключен**: `celery_app.conf.beat_schedule = {}` до завершения настройки парсеров.
8. **Пошаговая разработка**: сначала БД → парсеры → виджеты → новый функционал.
9. **Не создавать файлы без разрешения** — всегда спрашивать.
10. **Выполнять только запрошенные задачи** — не самовольничать.

---

## 10. Конфигурация окружения

- **OS**: Windows 11 Pro + Kali Linux
- **IDE**: Cursor AI
- **Claude**: используется как архитектор/аналитик, Cursor как реализатор
- **Deploy**: git push → Railway auto-build (Dockerfile: `alembic upgrade head && uvicorn`; `app/main.py` lifespan также вызывает `alembic upgrade head` перед bootstrap)
- **DB admin**: Supabase SQL Editor для прямых операций
- **Env vars** (Railway): DATABASE_URL, REDIS_URL, JWT_SECRET, CLAUDE_API_KEY, DECODO_USERNAME, DECODO_PASSWORD, DECODO_ENABLED, и др.

---

## 11. Файлы-источники истины

| Файл | Содержание |
|------|-----------|
| `Imperecta_Cursor_Project_Description.md` | Полное описание проекта для Cursor |
| `backend_full_audit_report.md` | Аудит backend (модули, сервисы, endpoints) |
| `parsers_audit.md` | Детальный аудит parser-стека |
| `imperecta_context.md` | Snapshot текущего состояния |
| `Imperecta_Database_Schema_v2.md` | Спецификация БД v2 |

---

## 12. Предыдущие промпты (все в /mnt/user-data/outputs/)

| Файл | Описание | Статус |
|------|----------|--------|
| Imperecta_DB_V2_Prompts.md | 4 промпта создания БД v2 | ✅ Выполнен |
| Imperecta_DB_V2_Additions.md | Дополнение схемы (crypto/fuel/commodity) | ✅ Выполнен |
| Imperecta_V2_Service_Migration.md | 5 промптов перевода сервисов на v2 | ⚠️ Частично |
| Imperecta_Manual_DB_Fix.sql | SQL для ручной фиксации БД | ✅ Выполнен вручную |
| Imperecta_Parser_Stabilization_3_Prompts.md | Cleanup engine.py + persistence + контракты | ✅ Выполнен |
| Imperecta_Parser_Step2_Verification.md | Persistence fixes + verification | ✅ Выполнен |
| Imperecta_Marketplace_Endpoints.md | Оживление marketplace CRUD | ✅ Выполнен |

---

## 13. Следующие задачи (приоритет)

### P0 (СЕЙЧАС): Починить scraping
- Запустить `POST /api/admin/pool/trigger-scrape`
- Проанализировать логи Railway
- Диагностировать почему fact_price=0 и scrape_logs=0
- Добиться хотя бы 1 успешного scrape с ценой

### P1: Тестирование на 5-7 маркетплейсах
- Убедиться что discovery + scraping работают end-to-end
- Проверить качество извлечения (title, price, currency, in_stock)
- Проверить что fact_price пишется корректно
- Проверить что scrape_logs содержат полезную диагностику

### P2: Виджет ОБЗОР РЫНКА (переделка)
- Убрать фильтры Волатильные/Трендовые/Растут/Падают
- Показывать реальные данные из fact_listing + dim_product
- Название товара вместо числового ID

### P3: Market data ingestion
- Включить Beat задачи для forex/crypto/commodities/fuel (по одной)
- Проверить что fact_currency_rate, fact_crypto_price, etc. заполняются
- Подключить виджеты Dashboard к новым данным

### P4: Перевод оставшихся сервисов на v2
- analytics, alerts, digests, dashboard — все ещё могут ссылаться на старые модели
- Проверить и мигрировать

---

## 14. Критические уроки из этого диалога

1. **Supabase не поддерживает DROP SCHEMA public CASCADE** — все DDL через ALTER/DROP TABLE.
2. **asyncpg требует одну SQL команду per execute()** — никаких точек с запятой.
3. **PostgreSQL ENUM (userplan) уничтожается при DROP SCHEMA** — кастовать в TEXT перед backup.
4. **Alembic может отметить миграцию как applied без фактического выполнения DDL** — нужен runtime guard в env.py.
5. **NOT NULL без DEFAULT** — при INSERT надо явно указывать значение (is_active=true в seeds).
6. **Миграции часто не работают с первого раза** — всегда проверять через Supabase SQL Editor.
7. **Beat schedule ДОЛЖЕН быть пустым** до полной валидации парсеров — иначе Celery запишет мусор.
