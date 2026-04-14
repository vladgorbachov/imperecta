# Parsers Audit — Imperecta

## 0. Актуализация (2026-04-04)

- `backend/app/modules/scraper/engine.py` отсутствует в репозитории (не используется).
- **Alembic head:** **`009_full_v2_schema_rebuild`** — идемпотентная полная DDL v2; цепочка включает **`005`** (CHECK + **`technical_error`**), **`006`** (**`status` `VARCHAR(50)`**), **`007`** (мета Alembic, таймауты), **`008`** (ширина **`version_num`**). ORM **`ScrapeLog.status`** — согласован с **`VARCHAR(50)`** и **`errors.SCRAPE_LOG_STATUSES`**.
- Каноничный runtime path парсера: `tasks -> discovery/service -> scraper_pool -> extractors`.
- `ScraperPool` является единственным fetch+extract facade.
- В **`service.py` (`GlobalScrapeService`)** персистенция pool-scrape:
  - **sync `Session`** (Celery); **`_run_coro_in_worker`** только для async `ScraperPool.scrape_product` (избегание `MissingGreenlet` в worker).
  - При **`result.success`:** немедленно **`listing.last_error = None`**, **`listing.consecutive_errors = 0`** (сброс устаревшей ошибки). При **`not result.success`:** инкремент `consecutive_errors` и **`last_error`**. Успех без тела `data` не увеличивает счётчик ошибок.
  - **`fact_price`:** пишется только если **`product_name_ok`** — непустой **`getattr(data, "product_name")` или `getattr(data, "title")`**, плюс **`price > 0`**, плюс непустая **валюта**. **`dim_product.name`:** если `product_name` пустой, но есть **`title`**, имя сохраняется с **title**; если `product_name` задан — обновление по прежним правилам placeholder/replace.
  - **`_today_date_id`:** `SELECT` существующей строки **`dim_date`** → при отсутствии — **`INSERT … ON CONFLICT (date_id) DO NOTHING`** (PostgreSQL) → **`session.flush()`** → повторный **`SELECT`** (идемпотентность, снижение deadlock при конкуренции за календарную строку).
  - **`last_in_stock`:** `result.in_stock` → `data.in_stock` → **`False`** для денормализации и UI.
  - `last_checked_at` на каждой попытке; **`scrape_logs` всегда** (при существующем листинге).
  - Логи: **`EXTRACTED →`** (сырые поля пула), **`FINAL PERSIST`** (перед commit), после успешного commit — **`SCRAPE COMPLETE listing_id=… status=… price=…`**, затем **`pool_scrape done`**.
  - Статусы лога: **`missing_critical_data`**, **`price_not_found`**, **`technical_error`** и др.; **`technical_error`** также пишется из **`tasks._persist_technical_error_log`** при исключениях в pool Celery-задачах. **`_determine_log_status`** при вызове из `scrape_product` получает **`data=`**; для unit-тестов без `data=` сохраняется ветка с **`has_title`/`has_price`**.
- Внутренние parser-контракты: `PoolScrapeResult` с quality-полями; `DiscoveryResult` в discovery.
- Beat: `celery_app.conf.beat_schedule = {}`.
- **Marketplaces:** как ранее; **POST `/deduplicate`** — заглушка.
- **Pool Celery tasks (`tasks.py`):** `_run_scrape_all_pool` — **синхронный** `sync_session_factory`, без `_run_async` для этого пути; discovery — async engine + `_run_async`.
- **Тесты:** `backend/tests/test_scraper_unit/` и `backend/tests/test_scraper_integration/` + `backend/tests/fixtures/scraper_fixtures.py`. Файлы **`test_scraper_persistence.py`** / **`test_scraper_extractors.py`** в корне `tests/` удалены.
- **Git:** не добавлять `--trailer "Made-with: Cursor"` в коммиты.

## 0.1) Архив актуализации (2026-03-31)

- См. выше; ранее указывалось `data.in_stock` — фактически у `ExtractedProduct` атрибута нет, используется безопасное чтение.

Этот раздел является источником истины для parser runtime. Ниже могут встречаться исторические блоки.

## 1. Scope аудита

Этот аудит покрывает весь функционал, связанный с парсингом и discovery данных:

- HTTP/API слой, который запускает discovery/scrape.
- Service слой, который извлекает и сохраняет данные в v2 schema.
- Celery tasks и orchestration.
- Extractors и движок скрапинга.
- Связанные доменные сущности (pool/marketplaces/admin), влияющие на пайплайн.
- Модели и таблицы, в которые записываются результаты.

Frontend намеренно не включён.

---

## 2. Полная карта файлов parser-стека

### Core orchestration
- `backend/app/main.py`
- `backend/app/workers/celery_app.py`
- `backend/app/workers/scheduler.py`
- `backend/app/workers/maintenance_tasks.py`
- `backend/app/workers/cleanup_tasks.py`

### Scraper module (ядро парсинга)
- `backend/app/modules/scraper/api.py`
- `backend/app/modules/scraper/tasks.py`
- `backend/app/modules/scraper/service.py`
- `backend/app/modules/scraper/discovery.py`
- `backend/app/modules/scraper/scraper_pool.py`
- `backend/app/modules/scraper/extractors.py`

### Pool/marketplace/admin integration
- `backend/app/modules/product_pool/api.py`
- `backend/app/modules/product_pool/service.py`
- `backend/app/modules/product_pool/schemas.py`
- `backend/app/modules/marketplaces/api.py`
- `backend/app/modules/marketplaces/service.py`
- `backend/app/modules/marketplaces/schemas.py`
- `backend/app/modules/core/api_admin.py`

---

## 3. Архитектура parser-потока

## 3.1 Runtime flow (high-level)

1. Админ/задача вызывает endpoint:
   - `/api/admin/discovery/trigger-all`
   - `/api/admin/discovery/trigger/{marketplace_id}`
   - `/api/admin/pool/trigger-scrape`
   - `/api/admin/trigger-scrape`
2. Endpoint ставит Celery task в очередь (`discover_*`, `scrape_*`).
3. Task создаёт отдельный async engine/session factory.
4. Discovery:
   - читает `DimMarketplace`,
   - обходит listing pages,
   - извлекает product URLs,
   - создаёт `DimProduct` + `FactListing`.
5. Scrape:
   - читает stale `FactListing`,
   - получает HTML (Decodo -> httpx -> Playwright),
   - извлекает данные (JSON-LD -> meta -> custom selectors -> auto-detect),
   - пишет `FactPrice`,
   - обновляет denormalized поля `FactListing`.

## 3.2 Layer priorities

### Fetch layer priority
- `decodo`
- `httpx`
- `playwright`

Если `requires_js=True`, `playwright` поднимается выше `httpx`.

### Extraction layer priority
- JSON-LD (`extract_from_jsonld`)
- meta tags (`extract_from_meta_tags`)
- custom selectors (`extract_with_custom_selectors`)
- auto-detect heuristics (`extract_auto_detect`)
- merge (`merge_results`)

---

## 4. Endpoints, пути, права доступа

## 4.1 Scraper admin API (`modules/scraper/api.py`)

Router:
- prefix: `/admin`
- auth: `get_current_superuser`

Endpoints:
- `POST /api/admin/trigger-scrape` -> enqueue `scrape_all`
- `POST /api/admin/discovery/trigger/{marketplace_id}` -> enqueue `discover_single_marketplace`
- `POST /api/admin/discovery/trigger-all` -> enqueue `discover_all_marketplaces`
- `POST /api/admin/pool/trigger-scrape` -> enqueue `scrape_all_pool_products`
- `GET /api/admin/scrape-activity` -> placeholder chart payload
- `GET /api/admin/error-distribution` -> placeholder chart payload

## 4.2 Product pool API (`modules/product_pool/api.py`)

Router:
- prefix: `/pool`
- auth: `CurrentUser` / `CurrentSuperuser` depending endpoint

Endpoints:
- `DELETE /api/pool/products/bulk` (stub)
- `GET /api/pool/products` (list global pool)
- `GET /api/pool/categories`
- `GET /api/pool/marketplace-stats`
- `GET /api/pool/stats`
- `GET /api/pool/search`

## 4.3 Marketplaces admin API (`modules/marketplaces/api.py`)

Router:
- prefix: `/admin/marketplaces`
- auth: `get_current_superuser`

Состояние (2026-03-31): рабочие endpoints поверх `MarketplaceService` и `dim_marketplace`: `GET ""` — список (формат админ-UI); `POST ""` / `POST /add-by-url` — добавление по URL; `POST /import-file`, `POST /import-text` — импорт URL построчно; `DELETE /{marketplace_id}`; `POST /recalculate-quotas`, `POST /set-requires-js`; `GET /{marketplace_id}/logs` — выборка из `scrape_logs`. `POST /deduplicate` — заглушка (сообщение о не реализованном merge).

## 4.4 Core admin endpoints, связанные с parsing data (`modules/core/api_admin.py`)

- `POST /api/admin/products/cleanup-invalid` -> удаляет невалидные URL из `fact_listing`
- `POST /api/admin/products/clear-pool` -> очищает `fact_price`, `fact_listing`, сбрасывает `products_in_pool`
- `GET /api/admin/diagnostics/pool` -> диагностика состояния parser/pool таблиц
- `GET /api/admin/api-health` -> конфигурация внешних провайдеров (Decodo и др.)
- `GET /api/admin/diagnostics/sample-products` -> sample из `dim_product`

---

## 5. Связи между модулями (dependency graph)

- `main.py` подключает роутеры parser-зависимых модулей: `scraper`, `pool`, `marketplaces`, `admin`.
- `marketplaces/api.py` -> `marketplaces/service.py` (`MarketplaceService`) -> `DimMarketplace`.
- `scraper/api.py` -> `scraper/tasks.py`.
- `scraper/tasks.py` -> `scraper/discovery.py` + `scraper/service.py` + `scraper/scraper_pool.py`.
- `scraper/service.py` -> `scraper/scraper_pool.py` + ORM (`DimProduct`, `FactListing`, `FactPrice`, `ScrapeLog`).
- `scraper/discovery.py` -> `scraper/scraper_pool.py` + ORM (`DimMarketplace`, `DimProduct`, `FactListing`, `ScrapeJob`).
- `scraper/scraper_pool.py` -> `scraper/extractors.py` + Decodo/httpx/Playwright.
- `workers/celery_app.py` подключает parser tasks.
- `workers/scheduler.py` currently disables beat (`{}`), so auto scraping is disabled.

---

## 6. Data model для parsing (куда пишутся данные)

Основные таблицы parser-контура:

- `dim_marketplace`
  - источник таргетинга discovery/scrape, flags: `is_active`, `requires_js`, custom selectors.
- `dim_product`
  - создаётся/обогащается discovery/scrape.
- `fact_listing`
  - ключевая сущность URL листинга/товара, хранит last_* поля.
- `fact_price`
  - исторические price snapshots (partitioned by `date_id`).
- `scrape_jobs`
  - джобы (в т.ч. discovery).
- `scrape_logs`
  - логирование результатов скрапинга.

Ключевые связи:
- `fact_listing.product_id -> dim_product.id`
- `fact_listing.marketplace_id -> dim_marketplace.id`
- `fact_price.listing_id -> fact_listing.id`

---

## 7. Детальный аудит parser-файлов

## 7.1 `modules/scraper/tasks.py` (orchestration layer)

Назначение:
- Celery bridge между API и бизнес-логикой.
- **Discovery:** `_run_async` + локальный async engine/session factory.
- **Pool scrape:** **`sync_session_factory()`** + синхронный `GlobalScrapeService.scrape_product` (без async сессии для listing/price/log).

Основные задачи:
- `discover_all_marketplaces`
- `discover_single_marketplace`
- `scrape_all_pool_products`
- `scrape_pool_product`
- `check_pool_completeness`
- aliases/deprecated:
  - `scrape_single` (deprecated)
  - `scrape_all` (alias)
  - `scrape_user_products` (delegates)

Наблюдения:
- Для **discovery** — локальный async engine per task run.
- Для **pool scrape** — один sync session на run; порог stale **`6h`**.
- Time limits: `scrape_pool_product` soft 120s / hard 150s.
- При необработанном исключении в pool-пути — **`_persist_technical_error_log`** пишет **`scrape_logs`** со статусом **`technical_error`** (нужны миграции **005–009**: CHECK, **`VARCHAR(50)`**, repair **`alembic_meta`**, полная DDL v2 в **009**).

## 7.2 `modules/scraper/discovery.py` (crawler)

Назначение:
- Обход marketplace listing страниц.
- Сохранение новых URL в пул.

Ключевые операции:
- `discover(marketplace)`:
  - создаёт `ScrapeJob(job_type='discovery')`,
  - считает текущий pool size и квоты,
  - обходит до `50` страниц,
  - вызывает `scrape_listing`,
  - сохраняет URL через `_save_product_urls`.
- `_save_product_urls`:
  - dedupe через `FactListing.compute_url_hash(url)`,
  - создаёт `DimProduct` placeholder + `FactListing`.

Наблюдения:
- При quota=0 используется "no explicit cap" (`10_000` ceiling).
- Обновляет `marketplace.last_discovery_*` + `products_in_pool`.

## 7.3 `modules/scraper/scraper_pool.py` (fetch+extract facade)

Назначение:
- Унифицированная точка входа для product/listing scraping.

Ключевые функции:
- `scrape_product(...)`:
  - fetch layer selection (`_layer_order`),
  - extraction pipeline `_extract_all_levels`,
  - overflow guard `MAX_VALID_PRICE = 9_999_999_999.99`.
- `scrape_listing(...)`:
  - извлекает `product_urls` + `next_page_url`.
- `_fetch_html_decodo/httpx/playwright`.

Наблюдения:
- Failover корректный и упорядоченный.
- Для `requires_js` приоритет Playwright повышается.
- Есть явная защита от numeric overflow.

## 7.4 `modules/scraper/extractors.py` (extraction engine)

Назначение:
- Универсальный extraction toolkit без marketplace hardcode.

Ключевые блоки:
- `extract_from_jsonld`
- `extract_from_meta_tags`
- `extract_with_custom_selectors`
- `extract_auto_detect`
- `extract_product_links`
- `detect_next_page`
- `parse_price_text`

Наблюдения:
- Сильный многоуровневый fallback.
- Строгая фильтрация product URL (исключение category/list/search и т.д.).
- `parse_price_text` поддерживает локали с `,`/`.` форматами.

## 7.5 `modules/scraper/service.py` (DB persistence layer)

Назначение:
- Связка `FactListing -> Scrape -> FactPrice` + `ScrapeLog` + обновление `DimProduct` (имя, картинка).

Ключевые сценарии:
- `scrape_product(listing_id)` — **синхронный метод**:
  - читает listing и marketplace config/selectors,
  - вызывает **`_run_coro_in_worker(self.pool.scrape_product(...))`**,
  - при **`result.success`** сбрасывает **`last_error`** и **`consecutive_errors`** (legacy cleanup),
  - при **`not result.success`** увеличивает **`consecutive_errors`** и выставляет **`last_error`**,
  - обновляет denormalized **`FactListing.last_*`** при наличии `data`,
  - **`FactPrice`:** только при **`product_name` или `title`**, **`price > 0`**, непустая **валюта**; для текущего дня — delete по `(listing_id, date_id)` + insert; **`price_change_pct`** от предыдущего снимка,
  - **`dim_product`:** при отсутствии `product_name` заполняет имя из **`title`**; при наличии `product_name` — обновление при placeholder (см. **`_should_replace_placeholder_name`**),
  - пишет **`scrape_logs`**, затем **`commit`**; при ошибке commit — **`rollback`** и возврат `persist_failed`.
- `_today_date_id`:
  - **`SELECT`** по **`date_id`** (сегодня UTC, YYYYMMDD),
  - если нет строки — **`INSERT` `DimDate` + `ON CONFLICT (date_id) DO NOTHING`**, **`flush`**, **`SELECT` снова** (или RuntimeError если строка так и не видна).

Наблюдения:
- Логирование: **`EXTRACTED →`**, **`FINAL PERSIST`**, после успешного commit — **`SCRAPE COMPLETE`**, **`pool_scrape done`**.
- Статусы `scrape_logs`: **`missing_critical_data`**, **`price_not_found`** и др. через **`_determine_log_status`**.
- Тесты: **`test_scraper_unit/`**, **`test_scraper_integration/`**, **`fixtures/scraper_fixtures.py`**.

## 7.6 Runtime contracts (current)

- `modules/scraper/scraper_pool.py`:
  - `PoolScrapeResult` содержит quality flags и список извлечённых/пропущенных полей.
- `modules/scraper/discovery.py`:
  - `DiscoveryResult` фиксирует обязательные статусы, тайминг и счётчики discovery.
- `modules/scraper/service.py`:
  - привязка `PoolScrapeResult` к `FactListing`, `FactPrice` и `ScrapeLog`.

---

## 8. Worker и scheduler аудит

## 8.1 `workers/celery_app.py`

- Включённые task modules:
  - `app.modules.scraper.tasks`
  - `app.modules.alerts.tasks`
  - `app.modules.digests.tasks`
  - `app.modules.market_data.tasks`
  - `app.workers.cleanup_tasks`
  - `app.workers.maintenance_tasks`

## 8.2 `workers/scheduler.py`

- Текущее состояние:
  - `celery_app.conf.beat_schedule = {}`
- Следствие:
  - нет автоматических cron-triggered scraping/discovery jobs.

## 8.3 `workers/maintenance_tasks.py`

Parser-adjacent maintenance:
- `refresh_materialized_views`
- `ensure_fact_price_partitions`

## 8.4 `workers/cleanup_tasks.py`

Retention cleanup:
- чистит `ScrapeLog` и связанные operational журналы.

---

## 9. Роутинг и entrypoint-интеграция

В `main.py` parser-контур подключён через routers:
- `marketplaces_router`
- `scraper_admin_router`
- `pool_router`
- `admin_router` (часть parser operations)

Все under `/api`.

Startup задачи:
- `_ensure_tables`
- `_ensure_superuser`
- `_setup_telegram_webhook`

Это важно, потому что schema mismatch может ломать login/parser startup.

---

## 10. Риски и узкие места

1. Качество извлечения зависит от marketplace-разметки; частичные результаты (`is_partial`) требуют мониторинга.
2. Дедупликация маркетплейсов по домену (`POST /deduplicate`) не реализована — возможны ручные дубликаты до отдельной задачи.
3. `api_admin` имеет часть placeholder payload'ов (`scrape-activity`, `error-distribution` через scraper api stubs).
4. При пустом beat parser-поток работает только вручную (это safe mode, но ограничивает automated freshness).

---

## 11. Код parser-файлов (выжимка по ключевым блокам)

Ниже приведены ключевые кодовые блоки parser-стека.

### 11.1 `backend/app/modules/scraper/api.py`

```python
router = APIRouter(
    prefix="/admin",
    tags=["scraper"],
    dependencies=[Depends(get_current_superuser)],
)

@router.post("/trigger-scrape")
async def admin_trigger_scrape(...):
    task = scrape_all.delay()
    return {"message": "Scrape task queued", "task_id": str(task.id)}

@router.post("/discovery/trigger/{marketplace_id}")
async def trigger_discovery(...):
    discover_single_marketplace.delay(str(marketplace_id))
    return {"status": "queued", "marketplace_id": str(marketplace_id)}
```

### 11.2 `backend/app/modules/scraper/tasks.py`

```python
@celery_app.task(name="discover_all_marketplaces")
def discover_all_marketplaces():
    async def _do() -> dict:
        engine, session_factory = _make_session_factory()
        scraper_pool = ScraperPool()
        ...
        crawler = DiscoveryCrawler(db, scraper_pool)
        for mp in marketplaces:
            res = await crawler.discover(mp)
```

```python
def _run_scrape_all_pool() -> dict:
    db = sync_session_factory()
    ...
    svc = GlobalScrapeService(db, scraper_pool)
    r = svc.scrape_product(lid)  # sync

@celery_app.task(name="scrape_all_pool_products")
def scrape_all_pool_products(self):
    return _run_scrape_all_pool()
```

### 11.3 `backend/app/modules/scraper/discovery.py`

```python
class DiscoveryCrawler:
    async def _save_product_urls(self, marketplace_id: UUID, urls: list[str]) -> int:
        for url in urls:
            url_hash = FactListing.compute_url_hash(url)
            exists = await self.db.scalar(select(FactListing.id).where(FactListing.url_hash == url_hash))
            if exists:
                continue
            product = DimProduct(...)
            listing = FactListing(...)
```

### 11.4 `backend/app/modules/scraper/scraper_pool.py`

```python
class ScraperPool:
    async def scrape_product(...):
        layers = self._layer_order(requires_js=requires_js)
        ...
        merged = self._extract_all_levels(html, url, custom_selectors)
        if merged.price is not None and (merged.price > MAX_VALID_PRICE or merged.price <= 0):
            merged.price = None
```

### 11.5 `backend/app/modules/scraper/extractors.py`

```python
def extract_product_links(soup: BeautifulSoup, base_url: str, custom_selector: str | None = None) -> list[str]:
    ...
    if _is_excluded_link(full_url):
        continue
    if _is_category_url(parsed.path):
        continue
    if not _looks_like_product_url(parsed.path):
        continue
```

### 11.6 `backend/app/modules/scraper/service.py`

```python
class GlobalScrapeService:
    def scrape_product(self, listing_id: UUID) -> PoolScrapeResult:
        listing = self.db.get(FactListing, listing_id)
        ...
        result = _run_coro_in_worker(self.pool.scrape_product(...))
        ...
        self.db.commit()
```

### 11.7 `backend/app/workers/scheduler.py`

```python
from app.workers.celery_app import celery_app

# All tasks are disabled until parsers are verified against v2 schema.
celery_app.conf.beat_schedule = {}
```

---

## 12. Итог

Parser stack в текущей версии:
- технически полнофункционален для ручного запуска (discovery + scrape + persistence),
- защищён от автоматического нежелательного запуска через пустой beat schedule,
- имеет детальную extraction-логику и failover layers,
- marketplace rows must exist in `dim_marketplace` (admin API) before meaningful discovery per marketplace.

Для production-эксплуатации ключевой фактор — осознанное включение beat и постепенный rollout источников.
