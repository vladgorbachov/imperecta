# Bug Research Log

Ежедневный автоматический баг-ресерч по бэкенду Imperecta (read-only). Каждый запуск добавляет новую секцию `## YYYY-MM-DD`. Находки внутри секции отсортированы по убыванию риска ущерба проду: critical > high > medium > low. Непочиненные находки переносятся в новую секцию с пометкой "переносится с YYYY-MM-DD".

---

## 2026-09-19

### CRITICAL — browser_render утекает процесс Chromium на каждый вызов (production, активно сейчас)

- **Приоритет**: critical
- **Источник**: Sentry (PYTHON-FASTAPI-1V) + Railway `celery worker` логи + чтение кода
- **Файлы**: [app/modules/scraper/service.py:146-157](../backend/app/modules/scraper/service.py#L146-L157) (`_run_coro_in_worker`), [app/modules/scraper/fetch_backends.py:309-337](../backend/app/modules/scraper/fetch_backends.py#L309-L337) (`_shared_browser`/`_BrowserHolder`), [app/modules/scraper/fetch_backends.py:357-407](../backend/app/modules/scraper/fetch_backends.py#L357-L407) (`_fetch_locked`)
- **Суть бага**: `_shared_browser()` кеширует Playwright `_BrowserHolder` в `WeakKeyDictionary`, ключ — текущий `asyncio` event loop, с расчётом на переиспользование браузера между вызовами внутри одного воркера. Но `scrape_product()` (service.py:857-880) на каждый листинг вызывает `_run_coro_in_worker`, который в типичном случае (нет уже запущенного loop в потоке Celery-задачи — обычный случай для sync-таска) делает `asyncio.run(coro)` — **новый event loop на каждый вызов**. Из-за этого кеш `_loop_browsers` никогда не даёт кэш-хит: на каждый `browser_render`-фетч запускается новый `async_playwright().start()` + `chromium.launch()` (новый Node-процесс Playwright-драйвера + процесс Chromium). Хуже: `holder.close()` вызывается только в exception-пути `_fetch_locked` (строка 396-397) или при ротации после `RENDER_PAGES_PER_BROWSER=12` страниц (строка 320-323) — оба условия недостижимы для свежего `holder`, у которого `pages_served` всегда стартует с 0. Значит при УСПЕШНОМ фетче браузер вообще никогда явно не закрывается, а когда `asyncio.run()` завершается и уничтожает свой loop, осиротевший процесс Chromium остаётся жить в контейнере — то есть **каждый успешный browser_render-фетч тоже течёт**, не только упавшие.
- **Сценарий ущерба прод**: при `CELERYD_CONCURRENCY` 2→3 (недавний бамп, см. память проекта) это 2-3 утечки процессов Chromium+Node в секунду на тиках, которые используют browser_render — файловый/процессный лимит контейнера исчерпывается быстро. Прямо сейчас это проявляется как `BlockingIOError: [Errno 11] Resource temporarily unavailable` на `fork_exec` при попытке запустить очередной Chromium (Sentry PYTHON-FASTAPI-1V, substatus=escalating, first seen 2026-09-18 23:37, 16+ событий и растёт). В логах `railway logs --service "celery worker"` подтверждено: в захваченном окне (~3 сек, ForkPoolWorker-45) КАЖДАЯ попытка browser_render для mediaworld.it падает с этой же ошибкой — т.е. backend сейчас фактически на 100% нерабочий для JS-тяжёлых листингов. Последствия: (а) провальные скрейпы увеличивают `consecutive_errors`/failure streak и после `LISTING_DEACTIVATE_AFTER_ERRORS` могут деактивировать ЖИВЫЕ листинги из-за ложных технических сбоев, а не реального ухода товара; (б) утечка процессов/FD будет расти дальше и рискует уронить весь celery-воркер по нехватке ресурсов — в коде уже есть комментарий (fetch_backends.py:270-272) о прошлом инциденте с OOM-килом воркера именно от параллельных рендеров; это тот же класс отказа, вернувшийся через другой путь.
- **План фикса (только описание, не выполнено)**: сделать жизненный цикл браузера независимым от одноразового per-call event loop — например, поднимать один долгоживущий поток с постоянным event loop для Playwright при старте воркер-процесса (переиспользуемый между тасками), вместо `asyncio.run()` на каждый вызов; либо явно закрывать/убивать процесс браузера в конце `_fetch_locked` перед возвратом на успешном пути, если известно, что текущий loop одноразовый.
- **ПОЧИНЕНО 2026-09-19**: `BrowserRenderBackend.fetch` теперь перебрасывает рендер через `asyncio.run_coroutine_threadsafe` на один долгоживущий per-process loop (`_get_render_loop`, daemon-поток `playwright-render-loop`); кеш `_loop_browsers`, ротация `RENDER_PAGES_PER_BROWSER` и семафор «один рендер за раз» стали процесс-wide; `atexit` закрывает браузер при рецикле чайлда. Регрессионный тест `test_browser_render_runs_on_persistent_render_loop`.

### HIGH — harvest_tick полностью не работает 22+ часа из-за 9 «битых» dim_marketplace.discovered_category_urls

- **Приоритет**: high
- **Источник**: Sentry (PYTHON-FASTAPI-1G) + sanity SQL (Supabase) + чтение кода
- **Файл**: [app/workers/harvest_tasks.py:173-190](../backend/app/workers/harvest_tasks.py#L173-L190) (`_shops_with_categories_sync`)
- **Суть бага**: запрос `WHERE dim_marketplace.is_active AND jsonb_array_length(discovered_category_urls) > 0` не учитывает, что колонка может содержать невалидный для `jsonb_array_length` JSON (не массив). Проверка `jsonb_typeof(discovered_category_urls) IS DISTINCT FROM 'array'` в Supabase показала 9 магазинов с `{}` (пустой JSON-объект) вместо `[]`: `azerty_nl, allegro_pl, ardes_bg, 1a_ee, alza_cz, alza_sk, allo_ua, altex_ro, alza_hu`. `jsonb_array_length()` на объекте кидает `InvalidParameterValue`, и **весь запрос падает целиком** — не только для этих 9 магазинов, а для ВСЕХ активных магазинов сразу, так как Postgres не гарантирует short-circuit порядок предикатов. Подтверждено в Sentry: PYTHON-FASTAPI-1G, substatus=escalating, 39 событий за 22+ часа, последнее — 2026-09-19 00:34, т.е. проблема активна прямо сейчас.
- **Сценарий ущерба прод**: `harvest_tick` (list-page price harvesting — ключевая часть стратегии coverage economics из памяти проекта) не может получить список магазинов с категориями вообще ни для одного магазина минимум 22 часа подряд — то есть весь pipeline харвеста цен со страниц листинга (list-page) стоит для ВСЕХ ~74 магазинов, не только девяти проблемных. Данные не портятся (запрос просто падает и таск завершается ошибкой), но цены с list-page не обновляются систематически всё это время — тихая деградация полноты/свежести цен.
- **Причина появления `{}` не установлена** (весь прикладной код всегда пишет `list`/`[]` через `cursor_store.set_discovered_category_urls`; дефолт колонки в БД корректный — `'[]'::jsonb`, миграция 010). Вероятно легаси-запись до появления discovery-фичи для этих 9 магазинов, либо ручная правка не тем типом.
- **План фикса (только описание, не выполнено)**: (а) точечный дата-фикс — `UPDATE dim_marketplace SET discovered_category_urls = '[]'::jsonb WHERE jsonb_typeof(discovered_category_urls) != 'array'` (нужно явное согласие пользователя, не выполнялся); (б) код-фикс — защитить запрос условием `jsonb_typeof(discovered_category_urls) = 'array' AND jsonb_array_length(...) > 0`, либо CHECK-констрейнт на колонку, чтобы не-массив нельзя было записать снова.
- **ПОЧИНЕНО 2026-09-19**: (а) дата-фикс применён — 9 строк `{}` → `[]` (обе пустые, потери нет; после фикса non-array = 0, 31/81 активных магазинов с категориями); (б) `_shops_with_categories_sync` считает длину через `CASE WHEN jsonb_typeof(...) = 'array' THEN jsonb_array_length(...) ELSE 0 END` — порядок вычисления гарантирован, не-массив = пусто. Тест `test_shops_with_categories_guards_non_array_jsonb`.

### MEDIUM — статистический таймаут на /api/pool/marketplace-stats

- **Приоритет**: medium
- **Источник**: Sentry (PYTHON-FASTAPI-18)
- **Файл**: [app/modules/product_pool/service.py:750](../backend/app/modules/product_pool/service.py#L750) (`get_marketplace_stats`), роут [app/modules/product_pool/api.py:195](../backend/app/modules/product_pool/api.py#L195)
- **Суть бага**: `asyncpg.QueryCanceledError: canceling statement due to statement timeout` на `SELECT ... FROM dim_marketplace LEFT OUTER JOIN fact_listing ... GROUP BY ...` — полный join+агрегация по всей `fact_listing` без покрывающего индекса/материализации, на той же нагруженной Micro Postgres, что уже упоминается в памяти проекта как потолок производительности. 6 событий с 2026-09-18, последнее ~3 часа назад на момент ресерча.
- **Сценарий ущерба прод**: пользовательский 500 на этом дашборд-эндпоинте под нагрузкой; данные не портятся, но это регулярно повторяющийся сбой минимум с 2026-09-18, и миграции 051/052 (pool read perf) этот эндпоинт, похоже, не покрывают.
- **План фикса (только описание, не выполнено)**: покрывающий агрегат/материализованное представление по аналогии с `mv_pool_stats`, либо ограничить выборку/пагинировать по активным маркетплейсам.
- **ПОЧИНЕНО 2026-09-19** (+ `/api/pool/categories` — тот же агрегат, 6-10 с на каждую загрузку Products, переведён на ту же MV): миграция 066 — `mv_marketplace_stats` (marketplace_id, listing_count, avg_price_eur; unique index на plain-колонке, cron `refresh-marketplace-stats` `5-59/10 * * * *` — со сдвигом от `refresh-pool-stats`); `get_marketplace_stats` теперь LEFT JOIN dim_marketplace → MV без GROUP BY по fact_listing. Применено в проде out-of-band (37 маркетплейсов, 3.09M активных листингов в MV). Тест `test_get_marketplace_stats_reads_preaggregated_view`.

### MEDIUM — устойчиво высокий blocked% у части магазинов за 24ч

- **Приоритет**: medium
- **Источник**: sanity SQL (`scrape_logs`, Supabase)
- **Суть находки**: за последние 24 часа `tsbohemia_cz` — 55/60 (91.7%) запросов заблокированы, `euro_com_pl` — 21/24 (87.5%), `cyberport_de` — 18/27 (66.7%), `mechta_kz` — 21/42 (50%). По памяти проекта `tsbohemia_cz` был переведён на `proxy_render` ещё 2026-09-17 — судя по текущему blocked%, перевод либо не даёт эффекта именно для этого сайта (усиленный anti-bot/фингерпринтинг), либо конфигурация не применилась.
- **Сценарий ущерба прод**: для этих магазинов сейчас почти нет успешного сбора цен — данные по их листингам устаревают/не обновляются с высокой частотой.
- **План фикса (только описание, не выполнено)**: разобрать `scrape_logs.error_message/error_category` по блокировкам этих магазинов, проверить фактически ли применяется `proxy_render`/нужный прокси-тир для `tsbohemia_cz`, при необходимости эскалировать гео/тир Decodo.
- **РАЗОБРАНО И ПОЧИНЕНО 2026-09-19 (переквалифицировано в HIGH)**: `proxy_render` НЕ применялся вообще. `scrape_logs` показал `blocked:browser_render`, `proxy_used=NULL` — рендер шёл локальным Chromium с Railway-IP. Причина: `access_policy`/`host_throttle` ключуются по сырому `netloc`; `dim_marketplace.base_url` хранится как apex (`https://tsbohemia.cz`), а листинги живут на `www.tsbohemia.cz` → `mode_for()` не находил хост → `direct`. Масштаб: **11 магазинов в `proxy_render` (~550k листингов: tsbohemia, euro_com_pl, mediaworld, sulpak, x-kom, cyberport, planeo cz/sk, mechta, euronics_ee, senukai) никогда не ходили через прокси**, плюс 9 direct-магазинов, у которых мимо проходил `rate_limit_delay`, и `klick_ee` (render). Тот же строгий `netloc`-матч в трёх экстракторах ссылок отбрасывал внутренние `www.`-ссылки как внешние (бьёт по category discovery). Фикс: `normalize_host()` (lowercase, strip `www.`) в обоих реестрах + `_site_host()` в экстракторах. Тесты `test_host_mode_is_www_insensitive`, `test_host_throttle_interval_is_www_insensitive`, `test_link_extractors_treat_www_as_same_site`.
- **Сопутствующий spend-guard**: после фикса ~550k листингов реально уходят на платный бэкенд (~$1.9/1k), а лимитер был только по RPS (10/с ≈ 864k/сутки теоретически). Добавлен суточный fleet-wide лимит `PROXY_PROVIDER_DAILY_CAP` (default 5000 ≈ $10/день; 0 = без лимита) поверх существующего счётчика `proxy_provider:usage:<YYYYMMDD>`; при исчерпании — честный скип `proxy_provider_budget` (как deadline-скип: `is_empty`, без падения на datacenter-фетч). Заодно: инфра-скипы (deadline/budget) больше **не** накручивают `failure_streak`/`consecutive_errors` — раньше deadline-скип мог довести живой листинг до деактивации (15). `/admin/parsing/proxy-usage` отдаёт `daily_cap`, `today_requests`, `cap_reached`.

### MEDIUM — всплеск reject_data `missing_name_or_currency` 2026-09-17 (не повторяется)

- **Приоритет**: medium
- **Источник**: sanity SQL (`reject_data`, Supabase)
- **Суть находки**: 2026-09-17 зафиксировано 1360 отказов с причиной `missing_name_or_currency` — на порядки больше обычного фона (единицы-десятки в другие дни/по другим причинам). За последние 24 часа этой причины в топе нет (текущий топ — `currency_country_mismatch`: 9, `currency_raw_too_long`: 8).
- **Сценарий ущерба прод**: разово потеряно/отклонено ~1360 карточек предложений за один день — вероятно, привязано к конкретному магазину или ран-джобу с проблемным парсингом имени/валюты в тот день. Не повторяется, но стоит подтвердить причину, если всплывёт снова.
- **План фикса (только описание, не выполнено)**: при повторении — определить магазин(и)/джоб через контекст `reject_data`, разобрать конкретный кейс парсинга.

### LOW/INFO — кластер "administrator command" разрывов соединений (инфра-событие, самовосстановилось)

- **Приоритет**: low
- **Источник**: Sentry (PYTHON-FASTAPI-1P, 1N, 1R, 1Q, 1S, 1T, 1M)
- **Суть находки**: 7 разных issue (sync session bind, matching engine, gate RPC writer) с ошибками разрыва соединения к Supabase pooler ("terminating connection due to administrator command" / connection closed) — все первое и последнее появление в одном узком окне ~3 часа назад на момент ресерча, без повторов. Похоже на разовый рестарт/maintenance пулера на стороне Supabase, а не баг приложения.
- **Сценарий ущерба прод**: транзиентные ошибки в моменте рестарта; sanity-проверки (сироты, скачки цен, невалидные листинги) — все чистые, признаков потери данных не найдено. Один из issue (PYTHON-FASTAPI-1S, `GateRpcError` в `_handle_gate_batch_rpc_error`) — на пути записи в gate; в этом read-only прогоне не проверялось, ретраится ли батч при `AdminShutdownError` — по чистым sanity-результатам похоже, что да.
- **План действий**: не требуется, если не повторится; при повторении — проверить, действительно ли gate-writer ретраит батч при обрыве адрес pooler-а, а не теряет его молча.

### LOW/INFO — data-ops: рост частоты "slow statement" в логах индекса поиска

- **Приоритет**: low
- **Источник**: Railway логи (`railway logs --service data-ops`)
- **Суть находки**: полный ре-индекс (`SELECT ... FROM dim_product WHERE is_active`, ~2.4-2.85М строк) занимает 5.5-6.5с, инкрементальные обновления (`... AND updated_at > $1 LIMIT 20000`) — 5-11с; почти каждый цикл обновления (~раз в 5 минут) в захваченном 3-часовом окне логов превышает порог алерта в 5с. Здоровье сервиса не пострадало (`/health` = ok), это соответствует уже задокументированному в памяти проекта "потолку Micro Postgres", не новая регрессия — но частота приближения к порогу растёт по мере роста пула (2.4М→2.85М строк за наблюдаемые 3 часа).
- **Сценарий ущерба прод**: пока нет прямого влияния на пользователей (индекс поиска успевает обновляться), но запас производительности сокращается по мере роста пула — стоит держать в поле зрения при решении о масштабировании БД.
- **План действий**: не требуется сейчас; мониторить тренд.

### Проверено чисто (без находок)

- **Тесты**: канонический раннер `backend/scripts/run_tests_local.sh -q` — **1653 passed, 0 failed, 22 skipped** (эталон 2026-09-18 был 1647/0/22 — прирост на 6 тестов, регрессий нет).
- **cron.job (Supabase)**: все 4 ожидаемых джоба на месте и активны — `retire-price-history` (10 4 1 * *), `refresh-pool-stats` (*/10 * * * *), `refresh-materialized-views` (0 * * * *), `ensure-fact-price-partitions` (0 0 * * *).
- **Sanity SQL**: 0 `fact_listing` с `last_price<=0` среди активных; 0 активных `fact_listing` с ценой без валюты; 0 "осиротевших" `fact_listing` без `dim_product` за последние 24ч; 0 записей `fact_price` за 24ч с `|price_change_pct| > 80`.
- **data-ops** (`/health`): `db: true`, `search_index.ready: true`, ~2.85М товаров в индексе.
