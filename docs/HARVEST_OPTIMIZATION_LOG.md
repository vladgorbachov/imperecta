# Harvest optimisation log (2026-09-19 →)

Программа из семи пунктов по ускорению сбора цен под бюджет Decodo
($49/цикл, standard+JS $0.65/1k, пейсинг $0.82/1k). По каждому пункту —
исследование «до» (аудит пути + замер), реализация, проверка «после»
(тесты + прод-цифры). Все цифры с источником.

## Базовая точка (2026-09-19 12:30 UTC)

- Пул 3.11M активных листингов; proxy-mode магазины — **2.56M** (pigu 1.05M,
  220_lv 315k, kaup24 247k, darwin 195k, comfy 105k, tsbohemia 99k,
  euro.com.pl 93k, mediaworld 89k, ultra 86k, sulpak 83k, x-kom 46k …).
  Источник: `dim_marketplace` × `fact_listing` (SQL через MCP).
- Приценено: 4 405 всего; в proxy-магазинах ~2 000.
- Категорий у proxy-магазинов: pigu 3, kaup24 3, comfy 1; 220_lv, darwin,
  tsbohemia, euro.com.pl, ultra, cyberport, mechta — **0**.
- Платных фетчей в день по гарду: ≈2 400 (59.26 / 0.82 / 30 дней).

## П.1 — пагинированный харвест с курсором

**До (аудит):** `harvest_tasks._harvest` брал `category_urls[:limit]` и качал
только первую страницу каждой категории — те же ~25 карточек на категорию
каждый тик; пагинация не использовалась вовсе, хотя `detect_next_page`
существует. Второй дефект: харвест не регистрировал `access_mode`/throttle
хоста (это делали только PDP-скрейп и discovery) → proxy-магазины
харвестились через direct и ловили 403, если процесс раньше не скрейпил
этот хост.

**Сделано:** курсор в Redis `harvest:cursor:{code}` (категория, next-URL,
страница, номер прохода, EMA карточек/страницу); переход по
`detect_next_page`; защита от петель (visited, `HARVEST_MAX_PAGES_PER_CATEGORY=500`
как loop-guard); при исчерпании бюджета прокси — стоп без сдвига курсора;
регистрация режима хоста через `fetch_params_from_marketplace`. Квота
страниц на запуск считается от размера пула (mv_marketplace_stats) и
измеренной доходности: цель — один проход пула за
`HARVEST_TARGET_PASS_DAYS=30` (период бюджета); pigu → 125 страниц/запуск
(формула в `pages_for_shop`). Тесты: `test_harvest_walks_pagination_and_persists_cursor`,
`test_harvest_budget_skip_keeps_cursor`, `test_pages_for_shop_walks_pool_once_per_pass`.

**После:** _заполняется по прод-логам (страниц/категорий за тик, yield_ema,
рост priced)._

## П.3 — категории из сайтмапов

**До (аудит):** энумератор оставлял только product-like URL и выбрасывал
остальное; «category»/«kategor» шарды стоят в `_SITEMAP_LATE_SHARD_HINTS`
(обрабатываются последними). Прямые curl-пробы сайтмапов pigu/220/
tsbohemia/euro/darwin/cyberport/mechta с локальной машины блокируются —
измерить состав без прокси нельзя; базовая точка — 0 категорий у 7 крупных
магазинов.

**Сделано:** `discovery/sitemap_categories.py`: структурный отбор
category-like URL (без query/фасетов/chrome, `_is_category_url`), product-
шарды пропускаются, category-шарды — в приоритете; слияние с уже открытыми
категориями (discovery первыми), кап 2 000 URL (размер JSONB-колонки, ~160 KB);
запись через META-дверь. В фан-ауте шарды складывают находки в Redis-set
`enumrun:{code}:{run}:cats`, финишёр публикует один раз. Тесты:
`tests/test_sitemap_categories.py`.

**После:** _заполняется после прогона энумерации по одному proxy-магазину._

## П.5 — одна попытка на платном слое

**До:** `FETCH_ATTEMPTS_PER_LAYER=3` для всех слоёв; Decodo биллит
неуспешные (681 из 9 879 за 30 дней = 6.9%) — каждый таймаут стоил до трёх
запросов.

**Сделано:** `PAID_BACKEND_ATTEMPTS=1` для `proxy_provider`; повтор — на
следующем тике листинга. Тест `test_paid_backend_gets_exactly_one_attempt`.

**После:** _доля failed в дашборде Decodo через сутки._

## П.2 — списки без JS

**До (аудит):** `_fetch_by_backend_once` перекрывал переданный `render_js`
политикой хоста (`wants_proxy_render`) — даже `fetch_static` (сайтмапы,
robots) с явным `render_js=False` у proxy_render-магазинов шёл с JS-рендером:
энумерация партии 7 (4 891 запросов 18.09) оплачена по JS-тарифу. Это и
есть измеренные «+27% к листу» в дашборде Decodo. Все proxy_render-магазины
имеют `requires_js=false` — режим выбирался из-за блокировок, а не из-за JS.

**Сделано:** `render_js: bool | None` — None = политика хоста, явный False
честно уходит в no-JS тариф; статика теперь без JS. Харвест пробует каждый
магазин раз в 7 дней (`harvest:listmode:{code}`): первая категория без JS и
с JS, no-JS побеждает, если даёт ≥ `REPEATED_STRUCTURE_MIN_COUNT` карточек и
не меньше, чем JS (`decide_list_mode`); дальше весь обход магазина идёт с
`render_js=False`. Гард бюджета стал считать стоимость, а не запросы:
no-JS фетч списывает 0.38/0.82 = 46% JS-запроса (`proxy_provider:cost:*`),
так что экономия превращается в дополнительные страницы. Тесты:
`test_decide_list_mode_rules`, `test_cost_weighted_usage_lets_nojs_buy_more`,
обновлённый `test_harvest_walks_pagination_and_persists_cursor`.

**После:** _доля магазинов с вердиктом nojs и фактическая цена за 1k в
дашборде через сутки._

## П.4 — cost-aware frontier для PDP

**До (замер):** первые 1 000 due-листингов очереди PDP (SQL по frontier):
887 proxy_render (платные), 111 direct, 2 render; из 887 платных лишь 126 в
match-группах. Очередь `last_checked_at ASC NULLS FIRST` слепа к стоимости:
89% каждого тика — платные карточки по давности, бесплатные магазины стоят
за ними.

**Сделано:** `scrape_stale_fanout` строит два frontier'а: FREE
(direct/render) — полный `shards×shard_size` по давности; PAID (proxy) —
только носители ценности (листинг в match-группе или с алертом), порядок
«алерт > группа > давность», лимит = остаток дневной квоты гарда / оставшиеся
тики дня (`_paid_quota_this_tick`). Массовая приценка proxy-магазинов —
задача харвеста (в ~30× дешевле за цену). Попутно: латентный `NameError` в
error-path `scrape_listing_batch` (неимпортированный
`capture_exception_if_initialized`). Тесты:
`test_scrape_stale_fanout_splits_free_and_paid_frontiers`,
`test_scrape_stale_fanout_skips_paid_when_budget_spent`,
`test_paid_quota_spreads_remaining_allowance_over_ticks_left`.

**После (первый прогон, 2026-09-19 06:00-07:30 UTC) — два дефекта, оба
починены:**
1. **Харвест не запускался вовсе.** `harvest_tick` раздавал задачи с новыми
   квотами (pigu 125, kaup24 30 …), но `harvest_list_pages` шли с приоритетом
   5 и ни разу не были получены воркером — все 6 детей заняты PDP-шардами
   (priority 2). Read-only срез брокера: priority-2 очередь 28 задач (9
   match-тиков, 3 harvest-тика, 6 harvest_list_pages…), priority-5 — 224,
   priority-8 — 434 (энумерация). Фикс: дети харвеста → priority 2
   (`21052a8`).
2. **Каждый PDP-шард — 840 с и 0 результатов.** Бесплатный frontier «самые
   старые» целиком состоял из ldlc.com (397k непроверенных, `direct`), а
   ldlc — тарпит: direct 3×25 с таймаут + browser_render 3×35 с = **183 с на
   листинг**, все впустую (`scrape_listing_batch_done assigned=250
   scraped_ok=0 scraped_failed=0`). Фиксы: (а) `timeout` больше не
   ретраится внутри одного фетча (ldlc: 183 → ≤60 с); (б) frontier с
   диверсификацией — не более одного шарда на магазин за тик и
   circuit-breaker: магазин с ≥20 попытками за час и 0 успехов получает
   5 пробных листингов, остальное — магазинам, которые отвечают;
   (в) реализация — LATERAL по магазинам на новом индексе
   `idx_listing_shop_checked_active (marketplace_id, last_checked_at NULLS
   FIRST) WHERE is_active` (068): EXPLAIN ANALYZE в проде **96 мс / 860
   буферов** против 9 136 мс / 150k буферов у оконной функции по всей
   таблице.
Открытый вопрос для Waldemar: ldlc.com (397k) под `direct` недостижим —
переводить на proxy (платно) или оставить на пробах 5/тик.

## П.6 — lastmod сайтмапов как сигнал изменений

**До (аудит):** `parse_sitemap_xml` читал только `<loc>` и hreflang-альтернативы;
`<lastmod>` выбрасывался, в `fact_listing` его негде было хранить; повторной
энумерации по расписанию не было (только ручные партии).

**Сделано:** миграция 067 `fact_listing.sitemap_lastmod` (nullable, применена
в проде мгновенно); парсер отдаёт `lastmod`; `fetch_sitemap_candidates(lastmod_out=)`;
энумератор при повторном проходе обновляет `sitemap_lastmod` у уже известных
листингов через META-дверь (`listing_sitemap_lastmod`, пайплайн 100/чанк);
frontier: `sitemap_lastmod > coalesce(last_checked_at, epoch)` — сигнал
«магазин говорит, что страница изменилась» — ценность 2 в платном frontier
(между алертом и группой) и первый порядок в бесплатном; beat
`sitemap-rescan` еженедельно (вс 03:00 UTC, priority 8) переэнумерирует все
магазины с пулом — новые товары + lastmod, одним no-JS запросом на файл.
Тесты: `test_parse_sitemap_xml_keeps_lastmod`, `test_parse_lastmod_formats`,
`test_lastmod_updates_are_gated_by_kind`, `test_sitemap_changed_signal_orders_frontier`,
`test_sitemap_rescan_tick_dispatches_populated_shops`.

**После:** _после первого воскресного пересбора — доля листингов с
`sitemap_lastmod`, честность lastmod по магазинам (distinct дат)._

## П.7 — JSON-эндпоинты витрин: аудит pigu-группы (60% proxy-пула)

**До (аудит в браузере, pigu.lt/lt/kompiuteriai/nesiojami-kompiuteriai):**
страница категории серверная — 60 карточек с ценами в HTML, пагинация
`?page=N` полным переходом (XHR нет), JSON-API не нужен: no-JS списки по
$0.30 покрывают pigu-группу. Но три дефекта экстрактора дали бы **0 цен** на
1.6M листингов:
1. Каждая карточка несёт уникальный класс `product-block-267212686` →
   структурная сигнатура (тег, классы) никогда не повторяется ≥6 → грид не
   найден, офферов 0. Фикс: токены классов с 3+ цифрами подряд исключаются из
   сигнатуры (Rust `is_instance_class` + Python `compute_element_signature`).
2. Цена размечена `299<sup>99</sup> €` → текстовые ноды «299» «99» «€» →
   склейка давала **99 €**. Фикс: приоритет атрибутам (`aria-label="299,99 €"`,
   `data-price`, `itemprop=price` + `priceCurrency`), в текстовом пути —
   склейка «целое» + «2 цифры» перед валютой.
3. Две текущие цены — «лояльная» (члены Pigu PLUS, `h-price--loyalty`) первой,
   публичная второй; старая — в `<s>`/`--old`. Фикс: зачёркнутые/old-hint
   исключаются, member-hint (loyal/member/club) — только как запасной вариант.
4. `<link rel=next>` битый (`https://pigu.lt/lthttps://…`) → обход обрывался
   бы на 1-й странице. Фикс: `detect_next_page` проверяет правдоподобие
   кандидата (тот же хост, один URL, не текущая страница) и умеет с 1-й
   страницы найти «2».
Тесты: Rust `attribute_price_prefers_public_over_member_and_old`,
`superscript_cents_join_in_text_path`, `instance_id_classes_do_not_break_the_grid_signature`;
Python `test_detect_next_page_rejects_malformed_rel_next_and_finds_page_2`.
Вердикт по п.7: для pigu-группы JSON-API не нужен; кандидаты на отдельное
исследование — darwin.md, x-kom (после «после» по п.1-2).

## Э — энумерация: шесть пунктов (2026-09-19)

Отдельная программа по запросу Waldemar («разбить на много потоков, более
эффективные алгоритмы, структуры, код»). Замеры «до» — прод, 19.09 утро.

**До (источники: логи воркера, EXPLAIN ANALYZE через MCP, queue_peek):**
- Один шард (3 подфайла, обрезан координатором до **10 000** URL:
  `max_urls // shards` с полом 10k — `raw=10000` в каждой строке лога)
  занимал **203–247 с** ≈ 45 пар/с.
- `gate.exec_write` на строку dim_product — **5.7 мс**, из них сам INSERT
  **1.8 мс**: остальное — чтение секрета из vault и `pg_attribute` на каждую
  ячейку, `format()`+`EXECUTE` на каждую строку.
- INSERT в fact_listing по случайному uuid4 — **7.1 мс/строку** (24 индекса,
  3.1 GB, shared_buffers 512 MB → index hit ratio 86.5 %).
- 9 индексов-дублей (`ix_fact_listing_*` рядом с `idx_listing_*`,
  `idx_product_name` 377 MB с 0 сканов, `idx_product_attributes` 0 сканов).
- Очередь: priority-8 (энумерация) **434 сообщения**, ни одно не получено
  за сутки — воркер на 2 детях (`-c 2` в start command перекрывал
  `CELERYD_CONCURRENCY=6`) всегда занят p2/p5.
- Парсинг сайтмапов: ElementTree на Python, хеширование и классификация
  50k URL в Python-циклах; весь tree скачивался целиком, потом писался.

**Сделано (616322d, 74db81a, этот коммит):**
1. Шард берёт всё, что перечисляют его подфайлы (`ENUMERATE_SHARD_MAX_URLS`
   = 3 × 50k по протоколу); `max_urls` — пол на прогон, не потолок шарда.
2. Отдельный Railway-сервис `celery worker-bulk` (`-Q bulk`, concurrency 3,
   Dockerfile с rust core) — `task_routes` шлют энумерацию/discovery в
   очередь `bulk`; у основного воркера снят `-c 2` → 6 детей (баннер
   `concurrency: 6 (prefork)` в логе деплоя 09c5b0f7). Настройки выставлены
   через Railway GraphQL (`serviceInstanceUpdate`), CLI их не умеет.
3. `gate.exec_write_rows` (069): HMAC на каждую строку сохранён, секрет
   читается раз на батч, типы колонок — раз на колонку, один
   `INSERT … SELECT FROM jsonb_array_elements($1)`; отказ гейта по паре —
   реджект пары, не падение батча.
4. uuid7 для новых product/listing id: fact_listing **7.1 → 2.0 мс/строку**,
   dim_product **1.8 → 0.35** (EXPLAIN ANALYZE, прод). 9 индексов-дублей
   сняты (070 — зеркало, в проде уже применено).
5. Rust `rust_core::sitemap`: quick-xml потоковый парсер, `url_hash(es)`,
   `product_like_path`, `category_like_url`; `walk_sitemaps` — генератор с
   prefetch=3: классификация/дедуп/запись документа N идут, пока качается
   N+1; дедуп `= ANY(array)` чанками 20k вместо IN-списков.
6. Дедуп-запрос — один параметр-массив на чанк (см. 5).

**Найдено по пути (при инспекции застрявших p8-сообщений, только чтение):**
432 из 434 — шарды pigu_lt старого прогона 08f200821aac; их подфайлы —
`ru/sitemap-products-*` 406, `*-images-*` 812, `lt/sitemap-products-*` 57,
служебные 16. Пул pigu — 1 045 288 листингов, **все под `/lt/`** (220_lv —
все `/lv/`, kaup24 — все `/et/`). Прогон «как есть» удвоил бы пул pigu
дублями `/ru/…` и сжёг ~1 200 платных запросов на image-сайтмапы.
Фикс — `sitemap_locale` (Rust `url_locale_segment`, `is_media_sitemap`,
`select_sitemap_subfiles`, `dominant_locale`, `locale_keep_mask` +
Python-двойники и parity-тесты): image/video-сайтмапы не ходим никогда;
на мультиязычном дереве координатор выбирает одну локаль — префикс пула
(≥80 % сэмпла), иначе язык страны, иначе первая в индексе — и передаёт её
шардам (`locale=`); шард без локали (старые сообщения) берёт префикс пула и
никогда не выбирает локаль по своим трём файлам; внутри файла URL другой
локали отбрасываются (`urls_skipped_locale` в итоге). Тесты:
`test_sitemap_locale.py` (оба движка), `TestMultiLocaleTree`,
`test_resolve_shards_drops_media_and_other_locales`.

**После (bulk-воркер, 09:20–10:30 UTC, логи деплоев d6681204/75ab8fe9/9ace00f4):**
- 434 сообщения перенесены в `bulk` (`LMOVE`, ничего не удалено); за 3 минуты
  до переноса основной воркер на 6 детях сам забрал 64 — p8 больше не голодает.
- image-шарды pigu (132 шт.): `empty_sitemap` за **80–120 мс**, без фетча.
- ru-шарды pigu: под правилом 9de80bd — фетч + отбрасывание 114 405 URL
  (11 шардов, ~10.7 с каждый, 0 вставок); под c286362+ — пропуск целиком
  без фетча. В пуле `/ru/`-строк **0**.
- lt-шарды pigu (19 шт. в первом окне): **11 500–15 000 вставок за 39–72 с**
  (≈250–380 пар/с против 45 пар/с «до»); всего пул pigu вырос
  **1 045 288 → 1 317 767** — 57 lt-файлов, которых старый прогон не дошёл.
  Старые сообщения несли `max_urls=10000` и обрывали шард после первого
  файла (raw 30 000 / обработано 15 000) — с c286362 шард всегда идёт до
  протокольного максимума.
- tsbohemia_cz: индекс 2759 файлов, из них 2150 `products-disabled` + 145
  reviews/consultations — 78 % мусора; шарды с продуктовыми файлами:
  3000 raw / 6–9 с. Прогон 4192c7d3191d остановлен (821 шард припаркован в
  `parked:bulk:tsbohemia_cz:4192c7d3191d`, в пул попало 2 строки), новый
  прогон пойдёт с noise-фильтром после сброса дневного лимита.
- euro_com_pl: 22 шарда, категорийные файлы 22 310 URL / 6.8 с, продуктовые
  до 17 405 URL / 244 с (4 306 вставок + 13 099 lastmod-обновлений через
  META-дверь — самая дорогая часть теперь запись lastmod, не парсинг).
- Бюджет: дневная квота 1 991 запрос (49 $/цикл ÷ 30 дней ÷ 0.82 $/1k)
  выбрана всплеском энумерации (2 408 к 10:28 UTC) — до 5d134cc это молча
  теряло прогоны, теперь ретрай в 00:00–00:10 UTC.
