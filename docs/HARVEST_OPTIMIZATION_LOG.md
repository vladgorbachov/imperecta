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

## П.2 — списки без JS (в очереди)

## П.4 — cost-aware frontier для PDP (в очереди)

## П.6 — lastmod сайтмапов как сигнал изменений (в очереди)

## П.7 — JSON-эндпоинты витрин (в очереди)
