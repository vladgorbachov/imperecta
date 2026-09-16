# Sitemap-first onboarding + list-page price harvesting — implementation plan

Status: DESIGN APPROVED (Waldemar, 2026-09-16), implementation not started.
Owner: backend agent. Resume here after quota reset — this file is the handoff.

## Why (context)
The 2026-09-16 full run proved card-BFS discovery cannot fill big shops:
comfy=39 of thousands (budget-bound), rozetka=0 with a WORKING Decodo channel
(sitemap_index fetched OK via proxy). Targets: >=80% of each shop's
assortment (floor, 100% is the goal), no pool cap, quality enforced, cost
controlled (~$1.9/1k Decodo requests measured; full run cost $1.51).

## Slice 1 — sitemap-full enumeration (onboarding)
1. New discovery phase `sitemap_enumerate` in `app/modules/discovery/`:
   reuse `sitemap_harvester` fetch path (it already cascades
   direct→proxy→render via fetch_adapter static path — rozetka worked).
2. Walk sitemap_index -> ALL product shards (lift SITEMAP_MAX_SUBFILES=15 /
   SITEMAP_MAX_URLS=50k to per-marketplace overrides; default up to 500k
   URLs, quotas are FLOORS not ceilings).
3. Classify URLs structurally (existing `_looks_like_product_url` +
   per-host learned patterns from already-known product URLs).
4. Bulk-insert fact_listing skeletons via existing gate path
   (`evaluate_ecommerce` listing_insert kind) with page_role='product',
   last_price NULL — cards are NOT fetched at onboarding.
5. Per-shop resume cursor in dim_marketplace (existing
   discovered_category_urls JSONB or a new sitemap_cursor JSONB field —
   JSONB serialization fixed in e342c4a).

## Slice 2 — list-page price harvesting (the economic backbone)
1. Rust core (`backend/rust_core`): new module `listing_page.rs` —
   extract (product_url, price_text, currency_hint, title) tuples from a
   category/list page using repeated-structure detection (port
   `extract_links_from_repeated_structure` + per-item price scan with
   existing `pricing` module). PyO3: `extract_list_offers(html, base_url)`.
2. New ingest path "price-from-list": update fact_price + denorm WITHOUT a
   card fetch; card fetch only on first-sight enrichment queue and on
   significant price moves (>10% or alert-relevant).
3. Scheduler: category pages become the scrape unit (new table or reuse
   fact_listing with page_role='listing' rows — they already exist from
   discovery); adaptive interval per category page.

## Slice 3 — adaptive backoff (approved)
fact_listing.scrape_interval_minutes: on unchanged price N cycles → ×2 up
to 7d cap; on change → reset to base. Trivial worker-side change in
GlobalScrapeService selection query + post-scrape update.

## Slice 4 — access-mode rollout
51/74 shops are bot-protected (probe map in memory
collection-economics-strategy). After slices 1-2 land, flip them to
proxy_render in batches of ~10/day via admin PATCH (service account in
.env works), watching Decodo spend (~$1.9/1k).

## Ops notes for the next session
- Decodo subscription is CANCELLED, disables ~2026-09-26 — user must renew.
- Worker memory: fixed by 08d11ee (render diet) + eeeaf1b (child recycle);
  if OOM returns, suspect sitemap XML parsing of huge shards — stream-parse.
- Run pipeline via POST /api/admin/parsing/run-pipeline
  {"marketplace_codes": [...]} with UI_SERVICE_LOGIN creds from .env.
- Tests: scratchpad testenv.sh pattern (inert CI env), ruff check . must
  stay clean, CI fully green as of 198bb7b.
