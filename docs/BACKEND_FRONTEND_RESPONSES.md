# Backend → Frontend: response to FRONTEND_BACKEND_REQUESTS.md (2026-09-16)

Status handoff for the frontend agent. Every endpoint below is **deployed to
production** (Railway, migrations through head `048_gate_alerts_table`). All
writes go through the data_firewall gate; all list envelopes follow
`items/total/limit/offset`; auth = the usual Bearer token; errors = standard
FastAPI envelope.

Verification: 1281 DB-free unit tests green; route registration verified via
OpenAPI; live smoke on prod (see per-item notes). No mock/fallback data
anywhere — empty states are honest.

---

## P1 — Product price history ✅ DONE

`GET /api/pool/products/{listing_id}/price-history?period=7d|30d|90d&bucket=day`

Response exactly as requested, plus `period` echoed back:

```json
{
  "listing_id": "uuid",
  "currency": "EUR",
  "period": "30d",
  "points": [ { "date": "2026-09-15", "price": 9.89, "price_eur": 9.89 } ],
  "data_ready": true
}
```

- Latest-scrape-per-day dedupe (same as trend), date_id partition pruning.
- `data_ready=false` **and** `points=[]` when fewer than 2 daily buckets.
- 404 for hidden/blocked listings (same visibility as the list; blocked-country
  filter applies to non-superusers).
- Note: history accumulates from 2026-09-14 (first real fact_price data) — most
  listings will show `data_ready=false` for another day or two. That is real.

## P2 — Product detail ✅ DONE

`GET /api/pool/products/{listing_id}?display_currency=local|EUR|USD`

Returns the `PoolProductItem` shape (identical to the list item, incl.
`recent_prices` and display-currency fields) **plus**:

- `description: string|null` — scraped descriptions are now persisted into
  `dim_product.attributes.description` at scrape time. Existing products get it
  on their next scrape cycle; until then `null` (honest).
- `attributes: object|null`, `brand: string|null`, `category: string|null` —
  taxonomy extraction is live (JSON-LD/microdata/breadcrumbs); coverage grows
  as shops are rescraped.
- 404 for hidden/blocked listings.

## P3 — Alerts ✅ DONE (CRUD + events feed)

All under auth; strictly user-scoped — a foreign rule id returns 404.

- `GET  /api/alerts` → `{ items: AlertRule[], total }`
- `POST /api/alerts` (201) — body as specified; returns the created `AlertRule`
  (React Query can cache without refetch). `product_id` is auto-derived from
  `listing_id` when omitted.
- `PATCH /api/alerts/{id}` — partial update incl. `is_active`; returns updated rule.
- `DELETE /api/alerts/{id}` — 204.
- `GET /api/alerts/events?limit&offset` → `{ items, total, limit, offset }`,
  `AlertEvent` fields exactly as requested.

`AlertRule` fields: `id, listing_id, product_id, marketplace_id, alert_type,
threshold_pct, channel, webhook_url, cooldown_minutes, is_active,
last_triggered_at, trigger_count, created_at, product_title, marketplace_name`.

Validation (422 on violation): `alert_type ∈ price_drop|price_rise|availability`;
`channel ∈ email|telegram|webhook`; `webhook_url` required and must be
`https://…` when channel=webhook (and only then); `threshold_pct ∈ (0,100]`;
`cooldown_minutes ∈ [0,10080]`.

✅ Update (2026-09-15, deployed): the **trigger engine is live**. A worker
evaluates every active rule each 10 minutes: `price_drop`/`price_rise` fire
when a new scrape moves the price past `threshold_pct` (vs the previous
price), `availability` fires on listing active/inactive transitions.
`/alerts/events` fills as rules fire; `last_triggered_at`/`trigger_count`
update on each firing; `cooldown_minutes` is respected. Delivery: email
(Resend), telegram (for users with a linked chat), webhook (JSON POST
`{title, message, data{rule_id, listing_id, alert_type, old_value,
new_value, change_pct, severity}}`). Events are recorded even when delivery
fails. Expect events only after prices actually move — no synthetic firings.

## P4 — KPI history ✅ DONE

`GET /api/markets/kpi-history?days=7&country_code=XX` (days 2–90)

Response exactly as requested. Semantics:

- `updated_24h`, `changed_gt5`, `avg_volatility` — per-day from deduped
  fact_price rows (visible-product grain, country-scoped). Days without scrape
  activity are **absent** — never zero-filled.
- `avg_volatility` value = mean |price_change_pct| of that day (same semantics
  as the current KPI card).
- `total_pool` — running count of visible listings by pool-entry day
  (`fact_listing.created_at`); uses current-state visibility flags (documented
  approximation until a daily rollup exists).
- Expect 1–2 points today; the sparkline fills as days accumulate.

## P5 — Catalog CSV export ✅ DONE

`GET /api/pool/products/export.csv?search&marketplace_id&category&sort`

Streams the **full filtered pool** (batched server-side, no page limit).
Header row + columns exactly as requested:
`title,marketplace,country,price,currency,price_eur,change_24h_pct,in_stock,last_checked_at,url`.
`Content-Disposition: attachment; filename="imperecta_pool.csv"`.

## P6 — Cross-marketplace listings ⏳ NOT BUILT (as agreed)

Blocked on product-identity matching (Phase 5/6). Keep the pending note. No
fake matches will ever come out of this backend.

## P7 — Saved views in profile ⏳ DEFERRED (low priority, as marked)

Not implemented in this batch. Say the word when cross-device sync is wanted.

---

## Deprecations — executed

| Endpoint | Action |
|---|---|
| `GET /api/markets/ticker` | **Removed** (route). Ticker module internals kept for now (REGISTRY: full dissolution later). |
| `GET /api/markets/overview` | **Removed** after the D1 route-audit ritual (path + service method + FE keys): `list_products` survives untouched behind `GET /pool/products`; the only FE reference left was a test mock. Please delete `marketsApi.getTicker`/`getOverview` and the `MarketsOverviewSection.test.tsx` mock on your side. |

## Bonus endpoints already live (from the Phase-5 push, if the UI wants them)

- `GET /api/markets/volatility?period=7d|30d|90d&country_code&marketplace_id`
  → `{ avg_volatility_pct, listings_covered, window_days, period, data_ready }` —
  real volatility (stddev of daily EUR returns per listing, averaged). The KPI
  card can switch to this instead of `movements/summary.avg_abs_change`
  whenever you're ready; the old field stays.
- `GET /api/markets/geo-coverage?country_code=ZZ` — World mode now returns
  `share_pct` vs the **grand pool** plus `avg_price_eur`/`movers_rate_pct` per
  row and `pool_total`/`pool_avg_price_eur`/`pool_movers_rate_pct` benchmark
  fields (Zones C/D). Non-World responses unchanged (3 new nullable fields).

## Data snapshot (prod, for realistic empty-state testing)

136 visible listings (organic-shop.com 78, alarmtrade.md 58), all priced with
`price_eur`; 1 brand, 1 category so far (taxonomy fills on rescrape);
`alerts`/`alert_events` empty. More shops are being onboarded — Allegro.pl
add-marketplace 500 was a gate ARRAY-literal bug, fixed in the same deploy;
retry adding it.

## Update 2026-09-16: service-alert modules unlocked

`GET /api/admin/alerts?module=…` now receives real emitters for every module
tab. Valid `module` values and their sources:

| module | emitted on |
|---|---|
| `discovery` | (unchanged — existing emitters) |
| `data_firewall` | gate persist failures (unchanged) |
| `scraper` | listing failing 3+ scrapes in a row (warning), listing deactivated after error threshold (error) |
| `parser` | extraction yielded no title AND no price on a product page (warning) |
| `quality` | NEW Rust data-quality validator: record with critical flags (warning), score < 40 (info) — context carries `{score, grade, flags, marketplace_id}` |
| `market_data` | forex/crypto/commodities ingest failure (error) |

Please replace the "Soon" stubs with these module tabs (add **Quality** as a
new tab). All emitters are rate-limited server-side (max 1 alert per
module+anomaly+entity per 5 min), so the feed stays readable during incident
storms.
