# Imperecta — Backend

**Актуально на:** 2026-06-03 (head `6701bba` + scoped scrape / extractor classifier fixes)  
**Стек:** Python 3.12, FastAPI 0.1.x API, SQLAlchemy 2 async/sync, Alembic, Celery, Redis, structlog.

---

## 1. Архитектурные правила

1. Домены в `backend/app/modules/<domain>/`.
2. `api.py` — тонкий слой; `service.py` — бизнес-логика без FastAPI.
3. HTTP → `AsyncSession` (`get_db`); Celery → `sync_session_factory`.
4. Async scrape в воркере → `_run_coro_in_worker()` (при активном loop — `ThreadPoolExecutor` + `asyncio.run`).
5. ORM только в `backend/app/models/`.
6. Structured logging; без `print()`.

---

## 2. `main.py`

### Lifespan (порядок)

| # | Действие |
|---|----------|
| 1 | `alembic upgrade head` — subprocess, env `DATABASE_URL`, timeout 600s |
| 2 | `ensure_superuser` — до 10 попыток, sleep 2s |
| 3 | `create_all` safety net |
| 4 | `create_task(_setup_telegram_webhook)` |

### Роутеры (`prefix="/api"`)

| Router | Prefix |
|--------|--------|
| `core.api_admin` | `/admin` |
| `admin.api_parsing` | `/admin/parsing` |
| `core.api_auth` | `/auth` |
| `core.api_telegram` | `/telegram` |
| `marketplaces.api` | `/admin/marketplaces` |
| `product_pool.api` | `/pool` |
| `market_data.api` | `/markets` |
| `dashboard.api` | `/dashboard` (+ nested `/markets`) |
| `user_products.api_products` | `/products` |
| `user_products.api_import` | `/import` |
| `analytics.api` | `/analytics` |
| `digests.api` | `/digests` |
| `ai_analyst.api` | `/ai` |

### Health

- `GET /health` — liveness для Railway.
- `GET /api/health` — `db`, `redis`, `db_pool` (size, checked_out, overflow).

---

## 3. `config.py` — Settings

| Группа | Поля |
|--------|------|
| Core | `database_url`, `redis_url`, `jwt_secret`, `jwt_algorithm`, expiration minutes/days |
| AI / email | `claude_api_key`, `claude_model`, `resend_api_key`, `email_from` |
| Market data | forex/crypto/commodities/fuel URLs, `goldapi_key`, `alpha_vantage_key`, timeout, retries |
| Telegram | `telegram_bot_token`, `telegram_webhook_secret` (**обязателен** с token), `app_url` |
| Proxy / Decodo | `proxy_list`, sticky, country routing, `decodo_*`, `decodo_enabled` |
| Deploy | `sentry_dsn`, `allowed_origins`, `app_env`, `port`, `debug` |
| Scraper | `discovery_max_pages_per_run` (5000), `discovery_no_quota_limit` (200000), `scrape_pool_batch_size` (1000), `scrape_pool_max_listings_per_run` (200000) |
| Bootstrap | `bootstrap_admin_email/password` (пара) |

**URL:** `postgresql://` → `postgresql+asyncpg://`.

---

## 4. Модули

### 4.1 `core`

- **Auth:** register, login, refresh, me, change-password.
- **Admin:** `/admin/stats`, claude-status, clear-pool.
- **Telegram:** webhook с проверкой secret header.
- **Plans:** entitlements (`app/entitlements/plan.py`).

### 4.2 `admin` — parsing control plane

**Файлы:** `api_parsing.py`, `parsing_admin.py` (`ParsingAdminService`).

**Auth:** все маршруты — `get_current_superuser`.

#### Endpoints `/api/admin/parsing`

| Method | Path | Назначение |
|--------|------|------------|
| GET | `/test-marketplaces` | Карточки для UI |
| POST | `/run-pipeline` | Создать job + enqueue Celery |
| POST | `/run-full-test` | Deprecated alias |
| GET | `/pipeline-runs` | История (limit query) |
| GET | `/test-runs` | Deprecated alias |
| POST | `/cancel-active-job` | Отмена + revoke Celery |
| GET | `/job-status/{job_id}` | Polling статуса |
| GET | `/worker-log-relay` | Redis log tail (`after`, `limit`≤200, `job_id`) |
| GET | `/users-detailed` | Список users (`limit`≤2000) |
| POST | `/users` | Создание user |
| PATCH | `/users/{id}` | Профиль, plan, language |
| PATCH | `/users/{id}/status` | activate/deactivate |
| PATCH | `/users/{id}/role` | superuser on/off |
| POST | `/users/{id}/reset-password` | Сброс пароля |
| DELETE | `/users/{id}` | Удаление |
| GET | `/marketplaces-detailed` | Пагинация `page`, `page_size`≤100 |
| GET | `/job-live-feed/{job_id}` | Steps из `scrape_logs` |
| GET | `/active-job` | Текущий running pipeline |

#### Stale job handling

`ParsingAdminService` при чтении active/status/runs:

- `STALE_PIPELINE_TIMEOUT_MINUTES = 30` — idle running → failed  
- `STALE_QUEUED_TIMEOUT_MINUTES = 5`  
- `STALE_DISPATCH_TIMEOUT_MINUTES = 10`  
- Metadata error: `stale_pipeline_timeout: idle_for_seconds=…`

#### Metadata contract (JSONB в `scrape_jobs.config`)

Рекомендуемая форма (backward-compatible):

```json
{
  "timings": { "discovery_ms", "scrape_ms", "persist_ms", "total_ms" },
  "summary": { "listings_created", "prices_saved", "errors_count" },
  "per_marketplace": [{ "marketplace_id", "domain", "status", ... }],
  "current_stage": "discovery|scrape|...",
  "last_activity_at": "ISO8601",
  "celery_task_id": "..."
}
```

### 4.3 `scraper`

См. `Imperecta_Parsing.md`.

**Discovery (`discovery.py`):**

- `DiscoveryCrawler.discover()` — job type `discovery`, quota-aware save.
- **Phase 0:** sitemap harvest + content-aware URL filter.
- **Phase 1:** category recon (BFS, `classify_page_role_for_discovery`, JSONB `discovered_category_urls`).
- **Phase 2:** product harvest from category URLs + pagination.
- Cooldowns: `SITEMAP_STALE_DAYS=3`, `CATEGORY_RECON_STALE_DAYS=7`, bad sitemap retry ~1h.

**Page analysis (`scraper_pool.py`):**

- `scrape_page_for_analysis(url, static_fetch=True)` — HTML + BeautifulSoup для discovery.
- `fetch_sitemap_candidates(base_url)` — robots.txt, nested sitemaps, XML validation, Playwright fallback.

**Classification (`extractors.py`):**

| Function | Used by | Strategy |
|----------|---------|----------|
| `classify_page_role_for_discovery` | `discovery.py`; **`merge_and_finalize`** (scrape) | Layer 1: `og:type`; Layer 2: JSON-LD `@type` (Product wins); Layer 3: `classify_page_role` fallback |
| `classify_page_role` | Layer 3 fallback only | JSON-LD + DOM repetition + price density |

**`merge_and_finalize`:** если role `listing`/`hub` → `merge_skipped_non_pdp_page`, пустой extract (раньше structural classifier давал false listing на PDP с блоками «похожие товары»).

Тесты: `test_schema_aware_discovery.py`, `test_pipeline_scoped_marketplaces.py`.

**Pipeline scrape scope (`orchestrator.py` + `tasks.py`):**

```text
metadata.marketplace_codes → discovery_phase
                          → _run_scrape_all_pool(marketplace_codes=...)
                          → JOIN dim_marketplace WHERE marketplace_code IN (...)
```

Standalone `scrape_all_pool_products` вызывает `_run_scrape_all_pool()` **без** `marketplace_codes` → full pool.

**Pipeline package:**

| Файл | Роль |
|------|------|
| `orchestrator.py` | `FullPipelineOrchestrator`; проброс `marketplace_codes` в scrape |
| `discovery_phase.py` | Discovery по active marketplaces |
| `job_completion.py` | Финализация parent job |
| `metadata_store.py` | Read/write metadata, `touch(stage=…)` |
| `cancellation.py` | Cancel checks, revoke task |
| `activity_pulse.py` | Heartbeat в metadata |
| `worker_log_relay.py` | Redis relay + logging handler |

### 4.4 Остальные модули

- **marketplaces** — CRUD, `requires_js`, discovery config JSONB.
- **product_pool** — search, stats, MV health.
- **user_products** — products + import; competitors API не в main.
- **market_data** — providers + `ingest_market_data`.
- **dashboard / analytics** — read aggregations.
- **ai_analyst** — sessions, Claude, api_logs.
- **alerts / digests** — tasks mostly stubs; alerts router не в main.

---

## 5. Celery

### `celery_app.py`

- Broker: `redis_url`; `rediss://` → `broker_use_ssl` CERT_NONE.
- **backend=None** — без result backend (Upstash limits).
- `broker_pool_limit=5`, retry policy.
- Includes: scraper, alerts, digests, market_data, cleanup, maintenance.

### `scheduler.py`

```python
celery_app.conf.beat_schedule = {}
```

### Задачи

| name | Модуль |
|------|--------|
| `discover_all_marketplaces` | scraper |
| `discover_single_marketplace` | scraper |
| `run_full_pipeline_test` | scraper |
| `scrape_all_pool_products` | scraper |
| `scrape_pool_product` | scraper (soft 120s / hard 150s) |
| `check_pool_completeness` | scraper |
| `ingest_market_data` | market_data |
| `ingest_commodities` | market_data |
| `cleanup_old_data` | workers |
| `refresh_materialized_views` | workers |
| `ensure_fact_price_partitions` | workers — rolling +3 months (`fact_price_YYYYMM`); дополняет Alembic `015` |
| alert/digest tasks | stubs |

---

## 6. Tiered scrape (`scraper_pool.py` + `service.py`)

**Migration 014:** `dim_marketplace.scrape_tier INTEGER NOT NULL DEFAULT 1`, CHECK `(1,2,3)`, index `idx_marketplace_scrape_tier`.

**Runtime:**

```text
GlobalScrapeService.scrape_product(listing_id)
  → mp = DimMarketplace
  → scrape_tier = int(mp.scrape_tier)  # default 1
  → ScraperPool.scrape_product(..., requires_js=mp.requires_js, scrape_tier=scrape_tier)
  → _layer_order(requires_js, scrape_tier)
```

| Constant | Value |
|----------|-------|
| `_SUPPORTED_SCRAPE_TIERS` | `{1}` — только tier 1 в проде |
| `_KNOWN_SCRAPE_TIERS` | `{1, 2, 3}` — контракт БД |

**Tier 1 layer order:**

- `requires_js=False`: decodo (if configured) → httpx → playwright  
- `requires_js=True`: decodo → **playwright** → httpx  

**Tier 2/3:** `NotImplementedError` с явным сообщением (misconfiguration не маскируется).

**Тесты:** `test_tiered_scrape_strategy.py`.

Параметр `scrape_tier` также на `_fetch_raw`, `_fetch_static`, `scrape_page_for_analysis` (discovery static fetch).

---

## 7. `GlobalScrapeService` (ключевые константы)

| Константа | Значение |
|-----------|----------|
| `LISTING_DEACTIVATE_AFTER_ERRORS` | 15 → `is_active=false` |
| `MAX_CURRENCY_RAW_LEN` | 50 |
| `_MAX_ABS_PRICE_CHANGE_PCT` | 9_999.9999 |

**Runtime DB repair** (legacy drift): при ошибке constraint/column — auto `ALTER` scrape_logs status VARCHAR(50) и CHECK.

**Persistence gate** (все условия для `fact_price`):

1. `product_name` или `title`  
2. `price > 0`  
3. `currency` non-empty  
4. `len(currency_raw) < 50`  
5. currency ∈ marketplace whitelist  

Логи: `EXTRACTED_DATA`, `PERSISTENCE_GATE`, `PRICE_UNCHANGED`, `LISTING_DEACTIVATED`, `pool_scrape_done`.

---

## 8. Entitlements API surface

`UserPlan`: trial, starter, business, pro, enterprise.  
`Feature.AI_ANALYST` — только PAID_FULL tier.  
Проверки в API guards и на фронте (`useEntitlements`, `AIAnalystRoute`).

---

## 9. Исключения и ошибки

- `app/common/exceptions.py` — доменные типы.
- Scrape: статусы `scrape_logs` — см. Parsing doc.
- API: HTTPException из parsing admin (`404` job not found).

---

## 10. Maintenance: `fact_price` partitions

**Проблема (prod, 2026-06-02):** migration `009` создала RANGE `fact_price`, но не все месяцы 2026 были покрыты → scrape INSERT падал.

**Migration `015`:** `fact_price_202606` … `fact_price_202612` + `fact_price_default` (DEFAULT partition — safety net, не постоянное хранилище).

**Celery `ensure_fact_price_partitions`:** создаёт партиции на **следующие 3 календарных месяца** (`CREATE TABLE IF NOT EXISTS`). Запускать по расписанию или после деплоя, пока beat пустой — вручную/enqueue.

---

## 11. Тесты

`backend/tests/` — API, scraper contracts, parsing admin.  
Запуск в CI / локально с test DB (не Supabase prod).

---

## 12. Источники истины

| Область | Путь |
|---------|------|
| Entry | `backend/app/main.py` |
| Settings | `backend/app/config.py` |
| Parsing API | `backend/app/modules/admin/api_parsing.py` |
| Parsing service | `backend/app/modules/admin/parsing_admin.py` |
| Persist | `backend/app/modules/scraper/service.py` |
| Tiered layers | `backend/app/modules/scraper/scraper_pool.py` (`_layer_order`) |
| Pipeline | `backend/app/modules/scraper/pipeline/` |
| Celery | `backend/app/workers/celery_app.py` |
| Partitions task | `backend/app/workers/maintenance_tasks.py` |
| Migration 015 | `backend/alembic/versions/015_fact_price_default_partition.py` |
| Entitlements | `backend/app/entitlements/plan.py` |

Связанные документы: `Imperecta_Architecture.md`, `Imperecta_Database.md`, `Imperecta_Parsing.md`.
