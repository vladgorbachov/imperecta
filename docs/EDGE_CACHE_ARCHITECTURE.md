# Stale-while-revalidate: снапшоты на edge + живая доводка

Решение Waldemar 2026-09-19: при 10-100k одновременных пользователей витрина
отдаёт готовые снапшоты мгновенно, а затем доводит страницу до актуальных
данных. Четыре слоя, все реализованы.

## Слой 1 — edge-кеш Cloudflare перед API и data-ops

- Зона `imperecta.com` в Cloudflare (Free), SSL Full (strict).
- `api.imperecta.com` → CNAME `l5lctepr.up.railway.app` (Proxied) — FastAPI.
- `data.imperecta.com` → CNAME `g4b7pa0t.up.railway.app` (Proxied) — data-ops.
- Cache Rule `edge-cache api+data`: `(http.host in {"api.imperecta.com"
  "data.imperecta.com"}) and (http.request.method eq "GET") and (not
  any(lower(http.request.headers.names[*])[*] == "authorization"))` →
  Eligible for cache, Edge TTL = «respect origin cache-control, bypass если
  нет», serve-stale-while-revalidating включён. Запросы с токеном идут
  мимо кеша (DYNAMIC) — персонализация суперюзера сохраняется.
- Zone Browser Cache TTL = Respect Existing Headers (дефолт 4 часа
  перебивал бы наш `max-age=60`).
- Origin решает, что кешируется: только **анонимные** ответы получают
  `Cache-Control: public, max-age=60, s-maxage=300, stale-while-revalidate=600`
  + weak `ETag`; запрос с `Authorization` → `private, no-store` (персонализация
  суперюзера не попадает в общий кеш). Плохой токен на публичном роуте
  деградирует до анонима, а не 401.
  - FastAPI: `app/common/public_cache.py` (`OptionalUser`, `PublicCache`,
    `PublicETagMiddleware`), роуты `/api/pool/*` (кроме CSV-экспорта),
    `/api/markets/*` (visualisation_calc), `/api/news`.
  - data-ops: `src/edge.rs` (`public_cache_layer`), все `GET /v1/*`.
- CORS: `imperecta.com`, `www.`, `app.`, `*.vercel.app`, localhost +
  `ALLOWED_ORIGINS` env (data-ops) / `ALLOWED_ORIGINS` (FastAPI).

## Слой 2 — серверные снапшоты

- `mv_pool_stats` (051/065), `mv_marketplace_stats` (066) — pg_cron каждые
  10 минут; `/pool/stats`, `/pool/marketplace-stats`, `/pool/categories`
  читают только их.
- data-ops in-memory поисковый индекс (delta-refresh) — `/v1/pool/search`,
  `/v1/pool/products?search=`.
- Кандидаты дальше: `kpi-history`, `volatility` (ещё считаются на лету).

## Слой 3 — SWR во фронте

- `src/lib/queryClient.ts`: `QueryClient` + персист публичных запросов в
  `localStorage` (dehydrate/hydrate, whitelist ключей, buster `swr-v1`,
  max-age 24ч). Пользовательские запросы (alerts, preferences, admin) не
  персистятся.
- `src/api/client.ts#publicClient` и `dataOpsClient` шлют запросы **без**
  `Authorization` — иначе CDN не кеширует. Все публичные read-вызовы
  (`products.ts`, `markets.ts`, `news.ts`) переведены на них; писать через
  них нельзя.
- Грид/поиск Products ходит в data-ops (`/v1/pool/products`, паритет
  контракта R4), FastAPI-двойник — fallback на 5xx/сеть.
- `staleTime` публичных запросов = 5 минут (окно снапшота CDN).

## Слой 4 — живая доводка

- `POST /v1/pool/products/refresh {ids ≤ 500, display_currency}` →
  `{items: PoolItem[], refreshed_at}` — PK-lookup строк, которые уже на
  экране; никогда не кешируется.
- `usePoolProducts`: сразу после прихода страницы и затем каждые 150 с
  (только при видимой вкладке) запрашивает refresh для id страницы и
  сливает свежие цены в кеш запроса (`mergeRefreshedItems`).

## Фронт на Vercel (stealth prod)

- Проект `imperecta-app` из `vladgorbachov/imperecta`, Root Directory
  `frontend`, Vite, `npm ci`, Node 22.
- Env: `VITE_API_URL=https://api.imperecta.com`,
  `VITE_DATA_OPS_URL=https://data.imperecta.com` (до переезда DNS — прямые
  Railway-URL).
- `frontend/vercel.json`: SPA rewrite, immutable `/assets`, `X-Robots-Tag:
  noindex`, лендинг `/ai.market.intelligence.agent` → `/login` (сайты вокруг
  продукта публично не публикуются).

## Проверка

```bash
curl -sI https://api.imperecta.com/api/pool/stats | grep -iE "cf-cache-status|cache-control|etag"
```

Второй запрос должен дать `cf-cache-status: HIT` (проверено 2026-09-19:
0.33 с через edge против 0.9-1.0 с в origin); с `Authorization` —
`private, no-store` и `DYNAMIC`.
