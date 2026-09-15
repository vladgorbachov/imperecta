# Frontend → Backend requests (UI redesign V1–V6, 2026-09-16)

Handoff document for the backend agent. The frontend for every feature below is
**already built and deployed**; each section names the exact frontend integration
point that is waiting for the endpoint. Until an endpoint lands, the UI renders an
honest empty/pending state (project rule: no mock / fallback / fake data).

Standing constraints (project law — do not deviate):
- All DB **writes** go through the `data_firewall` gate (signed field sets, explicit
  NOT NULL columns). User-data writes (alerts) need a gate door decision.
- **Reads** are operational SELECTs next to the consumer module (precedent:
  `currency/price_eur_resolver.py`), not through the gate and not through `data_export`.
- Respect existing grains: dashboard "visible product" = `is_active AND page_role='product'`;
  movements = `is_active` only; product_pool catalog = wider (see Imperecta_Architecture).
- Blocked-country filter (RU/BY) for non-superusers applies to any new pool-scoped read.
- Response envelopes below mirror existing conventions (`items/total/limit/offset`).

---

## P1 — Product price history (highest value, unblocks Product Peek chart)

`GET /api/pool/products/{listing_id}/price-history`

Query: `period` = `7d|30d|90d` (default `30d`), `bucket` = `day` (only value for v1).

Response:
```json
{
  "listing_id": "uuid",
  "currency": "EUR",
  "points": [
    { "date": "2026-09-01", "price": 6.49, "price_eur": 6.49 }
  ],
  "data_ready": true
}
```
- Source `fact_price` by `listing_id`, date_id-range pruning, latest-per-listing-per-day
  dedupe (same approach as `visualisation_calc/trend/`, but single listing, native
  currency + `price_eur` both returned).
- `data_ready=false` + empty points when fewer than 2 daily buckets exist.
- Frontend: `frontend/src/components/products/ProductPeek.tsx` — replaces the
  `recent_prices`-based mini chart (which stays as instant-render fallback).

## P2 — Product detail

`GET /api/pool/products/{listing_id}`

Response: one `PoolProductItem` (same shape as the list item in
`frontend/src/api/products.ts`) with `description` guaranteed present when scraped,
plus optional `attributes: object|null`, `brand: string|null`, `category: string|null`
(as taxonomy extraction matures). 404 for hidden/blocked listings (same visibility
rules as the list).
- Frontend: ProductPeek "Open full page" → future `/products/{id}` route; the peek
  itself can refetch fresh data by id instead of relying on the table row payload.

## P3 — Alerts (client price alerts; DB table `alerts` already exists)

CRUD (user-scoped, auth required; writes via gate discipline for user data):
- `GET  /api/alerts` → `{ items: AlertRule[], total }`
- `POST /api/alerts` body:
  ```json
  {
    "listing_id": "uuid | null",
    "product_id": "uuid | null",
    "marketplace_id": "uuid | null",
    "alert_type": "price_drop | price_rise | availability",
    "threshold_pct": 5.0,
    "channel": "email | telegram | webhook",
    "webhook_url": "https:// … | null",
    "cooldown_minutes": 60
  }
  ```
- `PATCH  /api/alerts/{id}` — partial update incl. `is_active`.
- `DELETE /api/alerts/{id}`.

`AlertRule` response fields: id, the fields above, `is_active`, `last_triggered_at`,
`trigger_count`, `created_at`, plus resolved display labels
(`product_title`, `marketplace_name`) so the UI needs no joins.

Events feed:
- `GET /api/alerts/events?limit&offset` → `{ items: AlertEvent[], total }` where
  `AlertEvent = { id, rule_id, alert_type, product_title, marketplace_name,
  old_price, new_price, currency, change_pct, triggered_at }`.
- The dashboard widget calls it with `limit=5`.

Frontend integration points:
- `frontend/src/pages/AlertsPage.tsx` — rules list, create dialog (form is built,
  submit disabled), events tab.
- `frontend/src/components/dashboard/AlertsStreamWidget.tsx` — latest events.
- `frontend/src/components/products/ProductPeek.tsx` — "Set alert" button
  (currently disabled) should POST with the peek's `listing_id` prefilled.

## P4 — KPI history (dashboard sparklines)

`GET /api/markets/kpi-history?days=7&country_code=XX`

Response:
```json
{
  "days": 7,
  "series": {
    "total_pool":    [ { "date": "2026-09-09", "value": 120 } ],
    "updated_24h":   [ … ],
    "changed_gt5":   [ … ],
    "avg_volatility":[ … ]
  }
}
```
- Daily snapshots; either computed on the fly from `fact_price`/`fact_listing` or from
  a small daily rollup — backend's call. Missing days are simply absent (no zero-fill
  fabrication).
- Frontend: `KpiCard` in `frontend/src/components/dashboard/MarketsOverviewSection.tsx`
  already accepts `spark?: number[]` and renders the sparkline only when data exists.

## P5 — Server-side catalog export

`GET /api/pool/products/export.csv` — same query params as `GET /pool/products`
(search, marketplace_id, sort), streams CSV of the **full filtered pool** (not just a
page). Columns: title, marketplace, country, price, currency, price_eur,
change_24h_pct, in_stock, last_checked_at, url.
- Client-side export of visible rows already ships (V4); this covers "export
  everything" for large pools.
- Frontend: `exportCsv` toolbar button in
  `frontend/src/components/products/PoolProductsTab.tsx` gains a second menu item.

## P6 — Cross-marketplace listings (later; needs product matching)

`GET /api/pool/products/{listing_id}/related` →
`{ items: [{ listing_id, marketplace_name, marketplace_domain, country_code, price,
currency, price_eur, in_stock, url }] }`
- Blocked on product identity matching across shops (Phase 5/6 territory). The peek
  section renders a pending note until then. Do not fake matches.

## P8 — Data-consistency report: products_in_pool in the parsing registry (2026-09-16)

`GET /admin/parsing/…marketplaces-detailed` returns `products_in_pool: 0` while the
pool actually holds products for that marketplace (`active_listings` shows 58 for
alarmtrade, `/pool/marketplace-stats` agrees with the pool). The frontend now
treats **`/pool/marketplace-stats` as the only source for per-marketplace product
counts** (admin Marketplaces table merges it in by domain) and ignores the
registry's `products_in_pool`/`active_listings` pair. Either populate
`products_in_pool` from the pool grain or drop both fields from the detailed
response — frontend no longer reads them.

## P7 — Optional: saved views in user profile

V4 stores table views in `localStorage`. If/when cross-device sync is wanted:
`GET/PUT /api/users/me/preferences` with an opaque JSON blob
(`products_views`, `products_density`). Low priority.

---

## Deprecation notices (frontend no longer calls these)

| Endpoint | Status |
|---|---|
| `GET /api/markets/ticker` | Zero UI consumers — HeaderTicker and TickerSettings were removed with the ticker feature. Retire or keep for API clients; frontend does not care. |
| `GET /api/markets/overview` | Zero UI consumers — the dashboard catalog moved to `/products`, which uses `GET /pool/products`. Before trimming, run the route-audit ritual (path + service method + FE response keys) per project lesson D1. |

## Notes

- `POST` responses should return the created entity so React Query caches can update
  without refetch.
- All new list endpoints: `items/total/limit/offset` envelope, stable ordering.
- Errors: standard FastAPI envelope; the frontend surfaces `common.error` + retry.
