# Imperecta — Backend

**Актуально на:** 2026-06-07 (head `4d42623`)  
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

- `DiscoveryCrawler.discover(deadline_monotonic?)` — cooperative 900s budget, inner job type `discovery`.
- **Phase 0:** sitemap (300s budget) + content-aware filter.
- **Phase 1:** category recon (BFS, schema-aware classifier).
- **Phase 2:** product harvest + `CATEGORY_CONVERGENCE_STREAK=3`.
- **Resumable save:** `sitemap_resume_offset`, batch 500, `partial_budget` на sitemap path.
- **Phase 2 cooperative deadline (`4d42623`):** `_headroom_deadline`, `_phase2_product_harvest` → `exhausted_budget`; `partial_budget` на category path.
- Timeouts: `SITEMAP_PHASE_BUDGET_SECONDS=300`, `DISCOVERY_PER_MARKETPLACE_BUDGET_SECONDS=900`, `SITEMAP_TIMEOUT_COOLDOWN_HOURS=24`.

**Page analysis (`scraper_pool.py`):**

- `scrape_page_for_analysis(url, static_fetch=True)` — HTML + BeautifulSoup для discovery.
- `fetch_sitemap_candidates(base_url)` — robots.txt, nested sitemaps, XML validation, Playwright fallback.

**Classification (`extractors.py`):**

| Function | Used by | Strategy |
|----------|---------|----------|
| `classify_page_role_for_discovery` | `discovery.py`; **`merge_and_finalize`** (scrape) | Layer 1: `og:type`; Layer 2: JSON-LD `@type`; Layer 2.5: microdata top-level `itemtype`; Layer 3: structural fallback |
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
| `discovery_phase.py` | Discovery по active marketplaces; `deadline_monotonic`; Z1 reap safety net |
| `job_completion.py` | Финализация parent job |
| `metadata_store.py` | Read/write metadata, `touch(stage=…)` |
| `cancellation.py` | Cancel checks, revoke task |
| `activity_pulse.py` | Heartbeat в metadata |
| `worker_log_relay.py` | Redis relay + logging handler |

### 4.4 Остальные модули

- **marketplaces** — CRUD, `requires_js`, discovery config JSONB.
- **product_pool** — search, stats, MV health; `display_currency` query → `CurrencyConverter`.
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

## 6. Display currency (`app/common/currency.py`, `app/common/marketplace_locale.py`)

| Компонент | Роль |
|-----------|------|
| `CurrencyConverter.load_latest` | Курсы из `fact_currency_rate` (max `date_id`); fallback — live `fetch_forex_rates("EUR")` |
| `normalize_display_currency` | `local` \| `EUR` \| `USD` |
| `apply_display_price_fields` | `(display_price, display_currency, conversion_available)` + **`local_currency_resolution`** |
| `resolve_local_currency` / `resolve_local_currency_from_parts` | TLD → country (`TLD_TO_COUNTRY`) → currency (`COUNTRY_TO_CURRENCY`); fallback `country_code`, then parsed listing currency |

**Режим `local` (`0fb6ac2`):**

- Предпочитает TLD домена над `dim_marketplace.country_code` (storefront country vs registration).
- Ответ включает `local_currency_resolution: { currency, source }` где `source` ∈ `tld`, `country_code`, `parse_currency`, `unknown`.
- При невозможности resolve → `local_currency_unavailable=true` (UI отключает local toggle).

**Принцип:** нет mock/fallback курсов — при отсутствии rate `conversion_available=false`.

**API с `display_currency` query:**

- `GET /api/products` (`user_products/api_products.py`)
- `GET /api/pool/*` (`product_pool/api.py`, `service._apply_display_currency`)
- `GET /api/dashboard/...` / markets overview (`dashboard/api.py`, `markets` API)

---

## 7. Tiered scrape (`scraper_pool.py` + `service.py`)

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

**Tier 1 layer order (httpx-first, `b6610ea`):**

- `requires_js=False`: **httpx** → decodo (if configured) → playwright  
- `requires_js=True`: httpx → **playwright** → decodo  

Экономия Decodo quota на SSR-магазинах; Decodo — после неудачи httpx.

**Tier 2/3:** `NotImplementedError` с явным сообщением (misconfiguration не маскируется).

**Тесты:** `test_tiered_scrape_strategy.py`.

Параметр `scrape_tier` также на `_fetch_raw`, `_fetch_static`, `scrape_page_for_analysis` (discovery static fetch).

---

## 8. `GlobalScrapeService` (ключевые константы)

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

## 9. Entitlements API surface

`UserPlan`: trial, starter, business, pro, enterprise.  
`Feature.AI_ANALYST` — только PAID_FULL tier.  
Проверки в API guards и на фронте (`useEntitlements`, `AIAnalystRoute`).

---

## 10. Исключения и ошибки

- `app/common/exceptions.py` — доменные типы.
- Scrape: статусы `scrape_logs` — см. Parsing doc.
- API: HTTPException из parsing admin (`404` job not found).

---

## 11. Maintenance: `fact_price` partitions

**Проблема (prod, 2026-06-02):** migration `009` создала RANGE `fact_price`, но не все месяцы 2026 были покрыты → scrape INSERT падал.

**Migration `015`:** `fact_price_202606` … `fact_price_202612` + `fact_price_default` (DEFAULT partition — safety net).  
**Migration `016`:** `dim_marketplace.sitemap_resume_offset` — resumable sitemap discovery.

**Celery `ensure_fact_price_partitions`:** создаёт партиции на **следующие 3 календарных месяца** (`CREATE TABLE IF NOT EXISTS`). Запускать по расписанию или после деплоя, пока beat пустой — вручную/enqueue.

---

## 12. Тесты

`backend/tests/` — API contract, scraper unit/integration, parsing admin.  
Конфиг: `backend/pyproject.toml` (`asyncio_mode=auto`, marker `integration`).

### Локальный запуск pytest

1. `pip install -r requirements.txt pytest pytest-asyncio httpx`
2. Postgres `imperecta_test` + Redis (например `docker compose up -d postgres redis`)
3. **`backend/.env`** с полным набором `Settings` (см. `app/config.py`) — корневой `.env` не подхватывается автоматически
4. `alembic upgrade head` на test DB
5. `cd backend && pytest tests -v` или `pytest -m "not integration"` для unit-only

**Блокер без env:** `conftest.py` импортирует `app.main` → `Settings()`; пустые `setdefault("", …)` дают ValidationError. CI использует GitHub Secrets `TEST_*` (см. `.github/workflows/ci.yml`).

**Не использовать Supabase prod** как test DB.

---

## 14. Детальная логика элементов

### 14.1 `main.py` — lifespan и routing

| Шаг | Логика |
|-----|--------|
| Alembic | Subprocess `alembic upgrade head`, env `DATABASE_URL`, timeout 600s; warn on fail, не блокирует навсегда |
| Superuser | `ensure_superuser` до 10× retry, sleep 2s — bootstrap admin из Settings |
| create_all | Safety net если migration пропустила таблицу |
| Telegram | Background `setWebhook` с secret header |
| Routers | 12 domain routers под `/api`; scraper/alerts routers **не** mounted |

**Health:** `/health` liveness; `/api/health` — ping DB, Redis, pool stats.

---

### 14.2 `core` — auth, admin stats, Telegram

| Компонент | Логика |
|-----------|--------|
| **Auth API** | Register → hash password; Login → JWT access+refresh; Refresh → rotate; Me → current user |
| **Admin stats** | Aggregates для Market Overview cards |
| **Telegram webhook** | Verify `X-Telegram-Bot-Api-Secret-Token`; reject if secret missing when bot token set |
| **Entitlements** | `plan.py`: `UserPlan` → `ServiceTier` → feature flags (AI only PAID_FULL) |

---

### 14.3 `admin/parsing_admin.py` — ParsingAdminService

| Метод | Логика |
|-------|--------|
| `trigger_full_pipeline_test` | `_fail_stale` → reject if active running → create `ScrapeJob(full_pipeline_test, running)` + metadata dispatching + optional `marketplace_codes` → commit (auto-repair job_type CHECK on IntegrityError) |
| `get_active_pipeline_job` | Latest running full_pipeline_test |
| `get_job_status` | `_fail_stale` → merge runtime activity → discovery progress helper |
| `cancel_active_pipeline_job` | Revoke Celery + parent failed + error `pipeline_cancelled_by_admin` |
| `_fail_stale_running_pipeline_jobs` | См. Parsing §18.12 — idle thresholds 5/10/30 min |
| `get_worker_log_relay` | Delegate to `fetch_relay_lines` |
| User CRUD | Standard CRUD on `users` with plan/language/role validation |

**Constants:** `TEST_PIPELINE_JOB_TYPE = 'full_pipeline_test'`, stale timeouts in minutes.

---

### 14.4 `admin/api_parsing.py`

Thin FastAPI layer: superuser guard → delegate to `ParsingAdminService`; map `ValueError` → HTTP 400/404; enqueue Celery on run-pipeline.

---

### 14.5 Pipeline package (детали — `Imperecta_Parsing.md` §18)

| Файл | Ответственность |
|------|-----------------|
| `orchestrator.py` | End-to-end async+sync flow |
| `discovery_phase.py` | Per-MP discovery + **Z1 reap** |
| `job_completion.py` | Parent job finalize (не Z1) |
| `cancellation.py` | Cancel detection + Celery revoke (не Z1) |
| `metadata_store.py` | JSONB read/write/touch |
| `activity_pulse.py` | Heartbeat 15s throttle |
| `worker_log_relay.py` | Redis 500-line buffer |

---

### 14.6 `scraper/tasks.py`

| Task | Логика |
|------|--------|
| `run_full_pipeline_test` | `_make_session_factory` → `FullPipelineOrchestrator.run` |
| `discover_all_marketplaces` | Async loop all active MP, no per-MP 900s wrapper |
| `discover_single_marketplace` | One UUID |
| `_run_scrape_all_pool` | Stale listing batch scrape; optional marketplace_codes scope |
| `scrape_pool_product` | Single listing, soft 120s / hard 150s |
| `scrape_all_pool_products` | Standalone full pool (no scope) |
| `check_pool_completeness` | Listings missing price/image |

**Async in worker:** `_run_async` / `_run_coro_in_worker` pattern.

---

### 14.7 `scraper/service.py` — GlobalScrapeService

| Этап | Логика |
|------|--------|
| Load | `FactListing` + `DimMarketplace` + product |
| Fetch | `ScraperPool.scrape_product(url, requires_js, scrape_tier)` |
| Extract | `merge_and_finalize` → PDP gate |
| Gate | name, price>0, currency, currency_raw len, whitelist |
| Persist | delete same-day price if changed → insert `fact_price` (+ `discount_pct`); else `no_change` |
| Failure | consecutive_errors++; at 15 → `is_active=false` |
| Logs | `_determine_log_status` → `scrape_logs` row |
| Drift repair | Auto ALTER scrape_logs on constraint mismatch |

---

### 14.8 `scraper/scraper_pool.py`

| Функция | Логика |
|---------|--------|
| `_layer_order` | Tier 1: httpx-first; tier 2/3 → NotImplementedError |
| `scrape_product` | Iterate layers until success or exhaust |
| `scrape_page_for_analysis` | Static HTML for discovery classify |
| `fetch_sitemap_candidates` | robots.txt → nested XML → Playwright fallback |

---

### 14.9 `scraper/discovery.py`

| Компонент | Логика |
|-----------|--------|
| `_headroom_deadline` | 85% of remaining MP budget for phase work; 15% for finalize |
| `discover(deadline_monotonic?)` | Inner job; cooperative budget; `partial_budget` on sitemap or Phase 2 |
| `_save_product_urls` | Batch 500; `(new_count, next_offset, exhausted)`; resume offset |
| `_filter_urls_by_role` | Sample/trust/reject sitemap filter |
| `_phase2_product_harvest` | Pagination + convergence + cooperative deadline → `exhausted_budget` |
| `_should_run_sitemap_harvest` | True if `sitemap_resume_offset > 0` or stale harvest |

---

### 14.10 `common/currency.py` + `marketplace_locale.py`

| Функция | Логика |
|---------|--------|
| `CurrencyConverter.load_latest` | Latest `date_id` from `fact_currency_rate`; empty → live forex |
| `normalize_display_currency` | Validate local/EUR/USD |
| `apply_display_price_fields` | Convert price; emit `local_currency_resolution` / `local_currency_unavailable` |
| `resolve_local_currency_from_parts` | TLD → country → ISO currency; sources: `tld`, `country_code`, `parse_currency`, `unknown` |

---

### 14.11 Остальные модули (кратко)

| Модуль | Логика |
|--------|--------|
| **marketplaces** | CRUD `dim_marketplace`; exposes requires_js, scraper_config |
| **product_pool** | Search/listings MV; applies display currency |
| **user_products** | User catalog CRUD + CSV import |
| **market_data** | Provider fetch → fact_* tables; ingest tasks |
| **dashboard/analytics** | Read-only aggregations for UI |
| **ai_analyst** | Claude sessions, api_logs, entitlement gate |
| **workers/maintenance** | `ensure_fact_price_partitions`, MV refresh, cleanup retention |

---

## 15. Источники истины

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
| Migration 015/016 | `backend/alembic/versions/015_*.py`, `016_*.py` |
| Display currency | `backend/app/common/currency.py`, `marketplace_locale.py` |
| Entitlements | `backend/app/entitlements/plan.py` |

Связанные документы: `Imperecta_Architecture.md`, `Imperecta_Database.md`, `Imperecta_Parsing.md`.
