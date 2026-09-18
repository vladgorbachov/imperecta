# Price-history retention — approved policy and rollout plan (2026-09-18)

Policy (approved by Waldemar): the pool database is PERMANENT — no resets,
ever. Products and prices are history. Deletion happens only inside this
framework.

## Framework

| Tier | Data | Lifetime | Granularity |
|---|---|---|---|
| Pool | dim_product, fact_listing | forever | row-level; vanished goods flip `is_active`, rows stay |
| Hot | fact_price (monthly partitions) | 12 months | every price change |
| Eternal | fact_price_weekly | forever | weekly open/close/min/max/avg + n_changes per listing+currency |
| Ops | scrape_logs, api_logs, reject_data | existing retention_delete windows | unchanged |

Cost math at full pool (~3-5M listings): raw prices ≈ 8-15 GB/year worst
case; the weekly tier compresses ~10-30x, so the eternal layer grows about
0.5-1 GB/year. Supabase disk is $0.125/GB-month — the framework keeps total
price storage roughly flat around the 12-month raw window.

## Skeleton (shipped, migration 059)

- `fact_price_weekly` table (SELECT for imperecta_app; written only DB-side).
- `maintenance.rollup_price_month(yyyymm)` — idempotent aggregation of one
  closed monthly partition.
- `maintenance.retire_price_partitions(keep_months=12)` — rollup → VERIFY
  weekly coverage (refuses to drop on any mismatch, raising instead) →
  DROP partition. Returns the retired list.
- pg_cron `retire-price-history`: monthly, day 1, 04:10 UTC. **No-op until
  2027-05** (oldest partition is 202604) — the skeleton is live but idle by
  construction.

## Remaining implementation (triggered work)

1. **Read-path union (before 2027-05):** price-history / volatility / trend
   readers must serve >12-month ranges from `fact_price_weekly` seamlessly
   (raw window UNION weekly tier). Natural home: the Rust data-ops read
   layer (see rust-data-module-decision); if that layer is not live by
   2027-Q1, implement in `visualisation_calc` + `product_pool.get_price_history`.
2. **First-retirement rehearsal (2027-04):** run
   `SELECT maintenance.rollup_price_month(202604)` manually, diff aggregate
   counts against raw, then let the May cron do the first real retirement.
3. **Monitoring:** service_alert on cron failure (cron.job_run_details has
   failures) — add a check to the daily bug-research task before 2027-04.
4. **Disk watch:** if raw fact_price approaches ~20-30 GB before 12 months
   of data exist, lower keep_months after a data-driven discussion — the
   function takes it as a parameter, no redeploy needed.
