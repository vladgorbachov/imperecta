# P6 — Кросс-шоп сравнение цен: спецификация для фронта

Статус бэка: **готово, live**. Сервис: `https://data-ops-production-8962.up.railway.app`
(отдельный Rust read-сервис; основной API не участвует).

## Аутентификация

Тот же Bearer JWT, что и для основного API (общий секрет, HS256).
`Authorization: Bearer <access_token>`. 401 — нет/просрочен токен.
CORS разрешён для `https://imperecta.pages.dev` и `http://localhost*`.

## Эндпоинты

### 1) GET `/v1/listings/{listing_id}/comparison`

Главный вход для UI: по `listing_id` строки из Products
(это `id` элемента в `/pool/products`).

Ответ 200:
```json
{
  "listing_id": "uuid",
  "match_method": "brand_model" | "gtin" | "title_exact" | "title_sim" | "unmatched" | null,
  "group": null | {
    "group_id": "uuid",
    "shops": 8,
    "min_price_eur": 27.98,
    "max_price_eur": 34.2,
    "offers": [ Offer, ... ]
  }
}
```
- `group: null` — товар ещё не смэтчен (или метод `unmatched`):
  показывайте состояние «Сравнение пока недоступно» без ошибки.
- `match_method: null` — товар ещё не обработан мэтчингом (очередь).
- 404 — listing_id не существует.

### 2) GET `/v1/groups/{group_id}/offers`

То же ядро по известному `group_id` (например, для шаринга/дип-линка).
404 — группа пуста или не существует. Формат = объект `group` выше.

## Offer

```json
{
  "listing_id": "uuid",
  "product_id": "uuid",
  "marketplace_code": "x-kom_pl",
  "marketplace_name": "x-kom",
  "country_code": "PL",
  "name": "A4Tech BLOODY R73 ...",
  "title_en": "..." | null,
  "external_url": "https://...",
  "last_price": 121.9 | null,
  "last_currency_code": "PLN" | null,
  "last_price_eur": 27.98 | null,
  "last_checked_at": "2026-09-18T10:01:31Z" | null,
  "match_method": "brand_model" | ...,
  "match_confidence": 0.9 | null
}
```
- Сортировка: `last_price_eur ASC NULLS LAST` — первый оффер с ценой =
  самый дешёвый. До 200 офферов.
- `last_price: null` — товар в пуле, цена ещё не собрана (harvest дойдёт):
  показывайте магазин с бейджем «цена обновляется», не скрывайте.
- Сравнивайте в EUR (`last_price_eur`); локальную цену показывайте
  вторично (`last_price` + `last_currency_code`).

## UX-рекомендации

- В таблице Products: бейдж «N магазинов» на строках, где сравнение есть
  (можно лениво: грузить comparison при раскрытии строки/попапе).
- В карточке сравнения: min/max/спред (`max-min`), выделить лучший оффер,
  ссылки `external_url` — target=_blank, rel=noopener.
- `match_confidence` < 0.85 — можно показать «возможное совпадение».
- Данные наполняются непрерывно: пул перематчивается (v2), цены и
  картинки едут от harvest-тика. Пустые сегодня группы наполнятся сами —
  никакого кеширования «навсегда» на фронте.

## Ошибки

`{"detail": "..."}` + статус: 401 (токен), 404 (нет данных),
500 (наша сторона — просто показать «попробуйте позже»).
