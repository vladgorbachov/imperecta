# Backend requests — 2026-09-18 (frontend session, consolidated)

Snapshot of everything the deployed frontend is currently blocked on or
degraded by. Measured today against production
(`imperecta-production.up.railway.app`, pool ≈ 1.44M listings) through a real
authenticated user session. Contract details live in
`docs/FRONTEND_BACKEND_REQUESTS.md` (P-numbers referenced below); this doc is
the prioritized "what hurts right now" list.

## 1. BLOCKER — POST /alerts rejects the in_app channel (P15)

The create-alert dialog now ships channel **toggles** (In-app / Email /
Telegram, several at once; webhook removed from the client UI per user
feedback). In-app is the default, so the most common submit today **fails**:

```
POST /api/alerts  → 422
{"detail":[{"type":"literal_error","loc":["body","channel"],
  "msg":"Input should be 'email', 'telegram' or 'webhook'","input":"in_app",
  "ctx":{"expected":"'email', 'telegram' or 'webhook'"}}]}
```

Payload the FE sends (already deployed, forward-compatible):

```json
{
  "listing_id": "…",
  "alert_type": "price_rise",
  "threshold_pct": 4,
  "channel": "in_app",            // legacy/primary; "email" > "telegram" > "in_app"
  "channels": ["in_app"],         // NEW: full enabled set
  "webhook_url": null,
  "cooldown_minutes": 60
}
```

Asks (full contract in P15):
1. Add `in_app` to the channel enum — smallest possible unblock, please ship
   first. `in_app` = no external delivery; the event row in
   `GET /alerts/events` **is** the delivery (header bell + dashboard stream
   already render it, with unread accounting on the FE).
2. Accept + persist `channels: string[]` (non-empty subset; webhook still
   valid via API for operators). Legacy payloads without `channels` →
   `channels = [channel]`. Return `channels` in rule responses.
3. Trigger engine: one event per fire, delivered to every channel in
   `channels` (`in_app` = no-op beyond the event row).
4. Backfill existing rules: `channels = [channel]`.

## 2. URGENT — product search latency (P12)

The alert dialog's product picker and the Products page share
`GET /pool/products?search=…`. Today's measurements (authenticated prod
session, limit=6):

| query           | latency |
|-----------------|---------|
| `lenovo`        | 7.55 s  |
| `len`           | 4.47 s  |
| `asus zenbook`  | 1.69 s  |
| `bofigo`        | 1.16 s  |
| no search, limit=25 | 1.09 s |

A typeahead needs **p95 < 300 ms**. Short/frequent tokens are the worst
(seq-scan-ish behavior on 1.44M rows). Asks (details in P12):
- `pg_trgm` GIN index on the searched columns (title + title_en), or a
  prefix-optimized path for short tokens.
- **Skip `count(*)` entirely when `search` is present and the caller only
  needs a page** — the dialog uses `limit=6` and ignores totals. An explicit
  `skip_total=true` param is fine; the FE will pass it.
- Estimated/capped totals + keyset cursors for the main table remain as
  specced in P12.

## 3. Alert trigger engine (P3 follow-up)

Rules exist (2 on prod) but no events have ever fired. The dashboard Alerts
widget, the Alerts→Events tab, and the new header bell (unread badge) are
all live and honest-empty. Once the engine ships, they light up with zero FE
changes. Please include `channels` fan-out from day one (see §1).

## 4. Still open from FRONTEND_BACKEND_REQUESTS.md

- **P9** — `PATCH /admin/service-alerts/{id}` `{resolved: true}`: the Resolve
  button in the admin Alerts module is deployed and waiting.
- **P10** — `category`/`brand` on the products LIST response: the Category
  column renders "—" until then.
- **P13** — `product_type` + `title_en`/`category_en`/`product_type_en` with
  the REQUIRED backfill of existing rows (translate DISTINCT values first).
  Type column and EN subtitles are live and show data as soon as fields
  arrive.
- **P11** (optional) — server-side favorites sync.
- **P6** — related listings for the product peek.

## Notes for planning

- The FE never needs a redeploy for any of the above — every field is
  optional/feature-detected.
- Priority from the operator's feedback: §1 (can't save an alert at
  all) → §2 (picker unusable at 4–8 s) → §3 → the rest.
