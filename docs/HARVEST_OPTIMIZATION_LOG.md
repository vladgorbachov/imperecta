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

**После:** _free/paid в `scrape_stale_fanout_done`, доля платных PDP в
scrape_logs, рост priced у direct-магазинов._

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
