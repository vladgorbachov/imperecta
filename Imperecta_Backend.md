# Imperecta — Backend (детальное описание)

**Актуально на:** 2026-05-28  
**Стек:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async + sync), Alembic, Celery, Redis, structlog.

---

## 1. Принципы архитектуры

1. **Модульность:** вся доменная логика в `backend/app/modules/<domain>/`.
2. **Тонкий API:** `api.py` — маршруты, DI, Pydantic-ответы; бизнес-логика в `service.py`.
3. **Два режима БД:** HTTP handlers → `AsyncSession` (`get_db`); Celery → `sync_session_factory` (psycopg2).
4. **Async в воркере:** вызов async scrape через `_run_coro_in_worker()` — отдельный event loop на вызов.
5. **ORM централизован:** `backend/app/models/` — единый metadata для Alembic.
6. **Без legacy-папок:** `app/api/`, `app/services/` не используются.

---

## 2. Точка входа: `main.py`

**Файл:** `backend/app/main.py`

### Lifespan

| Шаг | Функция | Поведение |
|-----|---------|-----------|
| 1 | `_run_alembic_upgrade_head` | `subprocess`: `alembic upgrade head`, 600s timeout |
| 2 | `_ensure_superuser` | `ensure_superuser` из `core`, retry до 10 |
| 3 | `_ensure_tables` | `Base.metadata.create_all(bind=engine)` |
| 4 | `_setup_telegram_webhook` | `asyncio.create_task`, не блокирует старт |

### Middleware

- `CORSMiddleware` — origins из `settings.origins_list`.

### Роутеры (prefix `/api`)

```text
/api/admin              → core.api_admin
/api/admin/parsing      → admin.api_parsing
/api/auth               → core.api_auth
/api/telegram           → core.api_telegram
/api/admin/marketplaces → marketplaces.api
/api/pool               → product_pool.api
/api/markets            → market_data.api (+ dashboard nested)
/api/dashboard          → dashboard.api
/api/products           → user_products.api_products
/api/import             → user_products.api_import
/api/analytics          → analytics.api
/api/digests            → digests.api
/api/ai                 → ai_analyst.api
```

### Служебные эндпоинты

- `GET /health` — liveness.
- `GET /api/health` — DB ping, Redis ping, pool statistics.

---

## 3. Конфигурация: `config.py`

**Класс:** `Settings` (pydantic-settings, env_file `.env` в корне репозитория).

### Группы настроек

| Группа | Ключевые поля |
|--------|----------------|
| Database | `database_url` (auto `+asyncpg`), pool settings |
| Redis | `redis_url` — Celery broker |
| Auth | `jwt_secret_key`, `jwt_algorithm`, access/refresh TTL |
| AI | `claude_api_key`, `claude_model` |
| Email | `resend_api_key`, `email_from` |
| Market data | URLs forex/crypto/commodities/fuel, API keys, timeout, retries |
| Telegram | `telegram_bot_token`, `telegram_webhook_secret`, `app_url` |
| Proxy / Decodo | `proxy_list`, `decodo_*`, sticky routing |
| Deploy | `sentry_dsn`, `allowed_origins`, `app_env`, `port`, `debug` |
| Scraper | `discovery_max_pages_per_run`, `discovery_no_quota_limit`, `scrape_pool_batch_size`, `scrape_pool_max_listings_per_run` |
| Bootstrap | `bootstrap_admin_email`, `password`, `name`, `language`, `plan` |

### Валидаторы

- Telegram token без `telegram_webhook_secret` → ошибка конфигурации.
- Bootstrap email/password — обязательны парой.

### Свойства

- `proxy_url`, `proxy_urls` — парсинг списка прокси.
- `origins_list` — split `allowed_origins`.

---

## 4. Database layer: `database.py`

- **Async engine** — для FastAPI (`create_async_engine`, sessionmaker async).
- **`get_db`** — dependency, yield session, commit/rollback по контексту.
- **`sync_session_factory`** — для Celery и sync persistence в scraper.
- **`Base`** — declarative base для всех моделей.

**Alembic env:** `backend/alembic/env.py` — явный commit после `run_sync`, чтобы async context exit не откатывал миграции.

---

## 5. Модули (детально)

### 5.1 `core`

| Файл | Назначение |
|------|------------|
| `api_auth.py` | register, login, refresh, me, change-password |
| `api_admin.py` | `/admin/stats`, claude-status, clear-pool |
| `api_telegram.py` | webhook handler |
| `auth/service.py` | JWT, password hashing, user lookup |
| `admin_service.py` | агрегаты для admin overview |
| `pool_maintenance.py` | очистка пула |
| `plans/service.py` | планы и лимиты |

### 5.2 `admin`

| Файл | Назначение |
|------|------------|
| `api_parsing.py` | 18 эндпоинтов parsing control plane |
| `parsing_admin.py` | `ParsingAdminService`: jobs, users CRUD, cancel |

**Базовый путь:** `/api/admin/parsing` — все с `get_current_superuser`.

Ключевые операции:

- `POST /run-pipeline` — job + `run_full_pipeline_test.delay()`
- `GET /active-job`, `GET /job-status/{job_id}`, `GET /job-live-feed/{job_id}`
- `GET /worker-log-relay?after=&limit=&job_id=`
- `POST /cancel-active-job`
- Users: list, create, patch, status, role, reset-password, delete
- `GET /marketplaces-detailed`, `GET /test-marketplaces`

### 5.3 `scraper`

См. `Imperecta_Parsing.md`. Кратко:

- `tasks.py` — Celery entrypoints
- `discovery.py` — двухуровневый discovery
- `service.py` — `GlobalScrapeService` (sync persist)
- `scraper_pool.py` — fetch + extract facade
- `extractors.py` — universal extraction
- `pipeline/` — orchestrator, phases, metadata, relay

`scraper/api.py` — **не** в `main.py` (legacy diagnostics).

### 5.4 `marketplaces`

CRUD `dim_marketplace`, квоты пула, scrape/discovery config JSONB, флаги `requires_js`, discovery selectors.

### 5.5 `product_pool`

Публичные эндпоинты: поиск, фильтры, категории, marketplace stats, health MV.

### 5.6 `user_products`

- `api_products.py` — CRUD user products, привязка к pool.
- `api_import.py` — CSV/XLS upload, mapping, batch create.
- `api_competitors.py` — **не** подключён в main.

### 5.7 `market_data`

- `ingestion.py` — оркестрация провайдеров.
- `providers/` — forex, crypto, commodities, fuel.
- `tasks.py` — `ingest_market_data`, `ingest_commodities`.
- `api.py` — read + manual ingest trigger.

### 5.8 `dashboard`, `analytics`, `digests`, `alerts`, `ai_analyst`

- **dashboard** — KPI, anomalies, markets widgets data.
- **analytics** — price history, comparisons, forecasts (service-layer aggregations).
- **digests** — read API; Celery generate tasks — stubs.
- **alerts** — service + tasks stubs; **router не в main**.
- **ai_analyst** — sessions, messages, streaming/status, `api_logs`, Claude client + monitor.

---

## 6. Entitlements

**Путь:** `backend/app/entitlements/`

Лимиты по плану: количество products, AI access, features flags. Используется в API и при проверке на фронте (`useEntitlements`).

---

## 7. Celery workers

### 7.1 `celery_app.py`

- Broker: `settings.redis_url`
- Result backend: `None` (результаты не хранятся в Redis)
- `task_track_started=True`
- Includes: scraper, alerts, digests, market_data, cleanup, maintenance

### 7.2 `scheduler.py`

```python
celery_app.conf.beat_schedule = {}
```

Все периодические задачи отключены до явного включения.

### 7.3 Таблица задач

| Task name | Модуль | Описание |
|-----------|--------|----------|
| `discover_all_marketplaces` | scraper | Все active marketplaces |
| `discover_single_marketplace` | scraper | Один marketplace by UUID |
| `run_full_pipeline_test` | scraper | Admin full pipeline |
| `scrape_all_pool_products` | scraper | Batch stale listings |
| `scrape_pool_product` | scraper | Один listing (soft 120s / hard 150s) |
| `check_pool_completeness` | scraper | Неполные listings |
| `check_alerts` | alerts | Stub |
| `generate_alert_ai_explanation` | alerts | Stub |
| `generate_weekly_digest` | digests | Stub |
| `generate_daily_digest` | digests | Stub |
| `schedule_weekly_digests` | digests | Stub |
| `schedule_daily_digests` | digests | Stub |
| `ingest_market_data` | market_data | Full ingest |
| `ingest_commodities` | market_data | Commodities only |
| `cleanup_old_data` | workers | Retention scrape_logs, api_logs, chat, events |
| `refresh_materialized_views` | workers | `mv_daily_price_summary`, `mv_marketplace_health` |
| `ensure_fact_price_partitions` | workers | Партиции на 3 месяца вперёд |

---

## 8. Паттерны кода

### 8.1 Async в Celery

```text
Celery task (sync)
  → sync_session_factory()
  → GlobalScrapeService.scrape_product()
       → _run_coro_in_worker(ScraperPool.scrape_product(...))
  → commit / scrape_logs
```

### 8.2 Discovery в Celery

Локальный async engine + `_run_async(coro)` для `discovery.py` (не общий app engine).

### 8.3 Ошибки скрапа

Необработанное исключение в pool task → `_persist_technical_error_log` со статусом `technical_error`.

### 8.4 Логирование

- `structlog` в pipeline/orchestrator.
- Стандартный `logging` в остальных модулях.
- Запрещён `print()` в production path.

### 8.5 Исключения

`backend/app/common/exceptions.py` — доменные исключения; API переводит в HTTP.

---

## 9. Admin parsing — контракт job

**Тип job:** `full_pipeline_test` (parent `scrape_jobs`).

**Metadata (JSONB в config):** stage (`dispatching` | `discovery` | `scrape` | `persist` | `completed`), `celery_task_id`, marketplace filter, counters, `last_activity_at`, discovery_errors, per-marketplace stats.

**Отмена:** `cancellation.is_pipeline_job_cancelled`, `revoke_celery_task`.

**Завершение:** `job_completion.complete_pipeline_job` — финальный status, агрегированные метрики, timing.

---

## 10. Зависимости и качество

- **Lint:** ruff (`I` import order, типизация).
- **Типы:** annotations на все public functions.
- **Тесты:** pytest в `backend/tests/` (API, scraper contracts).

---

## 11. Файлы-источники истины

| Область | Путь |
|---------|------|
| Entry | `backend/app/main.py` |
| Settings | `backend/app/config.py` |
| DB sessions | `backend/app/database.py` |
| Models | `backend/app/models/*.py` |
| Parsing API | `backend/app/modules/admin/api_parsing.py` |
| Pipeline | `backend/app/modules/scraper/pipeline/` |
| Tasks | `backend/app/modules/scraper/tasks.py` |
| Celery | `backend/app/workers/celery_app.py` |

Связанные документы: `Imperecta_Architecture.md`, `Imperecta_Database.md`, `Imperecta_Parsing.md`.
