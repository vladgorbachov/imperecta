# Admin alert endpoints — frontend handoff

Operational reference for the admin alerts UI. All discovery service alerts are
written with `module = "discovery"` and `alert_class = "service"`.

## Endpoints

### `GET /api/admin/service_alerts`

**Auth:** superuser only (`get_current_superuser`).

**Purpose:** operational service-health alerts (`service_alerts` table).

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `module` | string | — | Filter by module (e.g. `discovery`) |
| `submodule` | string | — | Filter by submodule (e.g. `bfs_walker`) |
| `severity` | string | — | `info`, `warning`, `error`, or `critical` |
| `resolved` | enum | `all` | `open` (resolved_at IS NULL), `resolved`, or `all` |
| `limit` | int | 50 | 1–200 |
| `offset` | int | 0 | pagination offset |

**Response shape:**

```json
{
  "items": [
    {
      "id": "uuid",
      "alert_class": "service",
      "module": "discovery",
      "submodule": "bfs_walker",
      "severity": "warning",
      "anomaly_type": "phase1_budget_exhausted_no_publish",
      "message": "…",
      "context": { "marketplace_id": "…", "queue_len": 12 },
      "triggered_at": "2026-06-17T12:00:00+00:00",
      "resolved_at": null
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

### `GET /api/admin/analytic_alerts`

**Auth:** superuser only.

**Purpose:** client price-alert events (analytic class; read over `alerts` /
`alert_events`).

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `alert_type` | string | — | Client alert type |
| `severity` | string | — | Event severity |
| `user_id` | uuid | — | Owning user |
| `limit` | int | 50 | 1–200 |
| `offset` | int | 0 | pagination offset |

**Response:** paginated `alert_events` joined to `alerts`; each item includes
`alert_class` (typically `"analytic"`), `alert_type`, `user_id`, price deltas,
`triggered_at`, `read_at`.

## Severity scale

| Severity | UI guidance |
|----------|-------------|
| `info` | Informational; no immediate action |
| `warning` | Degraded path or anomaly; investigate when recurring |
| `error` | Operation failed or data path blocked; needs attention |
| `critical` | Persistent write failure or inconsistent persisted state |

## Resolved semantics

- `resolved_at = null` → **open** alert (use `resolved=open` filter).
- `resolved_at` set → **resolved** (use `resolved=resolved` filter).

## Alert class signature

| `alert_class` | Source table(s) | Endpoint |
|---------------|-----------------|----------|
| `service` | `service_alerts` | `/api/admin/service_alerts` |
| `analytic` | `alert_events` + `alerts` | `/api/admin/analytic_alerts` |

Do not mix classes on one endpoint; filter `module=discovery` on service alerts
only.

---

## Discovery service alerts (module = `discovery`)

Authoritative list from `emit_discovery_service_alert` call sites in
`backend/app/modules/discovery/`. Submodule names match the first argument to the
emitter.

### budget_governor

| anomaly_type | severity | Signals |
|--------------|----------|---------|
| `resume_index_desync` | warning | Category backlog detectors disagree (`resume_index` vs `categories_len`) |

### orchestrator

| anomaly_type | severity | Signals |
|--------------|----------|---------|
| `meta_snapshot_write_failed` | critical | Success-path `dim_marketplace` snapshot write failed after retry |
| `discover_status_inconsistent` | warning | `persisted_listings > 0` but terminal status is `no_categories` |
| `discover_exception` | error | Unhandled exception in `discover()` outer handler |
| `finalize_write_rejected` | error | Child finalize `scrape_jobs` UPDATE rejected by META gate |

### gate_persist

| anomaly_type | severity | Signals |
|--------------|----------|---------|
| `pool_batch_commit_failed` | error | Gated pool batch commit raised (re-raised after alert) |
| `pool_batch_total_reject` | warning | Entire pool batch rejected by data firewall (0 inserted) |

### cursor_store

| anomaly_type | severity | Signals |
|--------------|----------|---------|
| `resume_index_oob` | warning | `category_resume_index` exceeds `discovered_category_urls` length |
| `frontier_deserialize_failed` | warning | Corrupt `recon_frontier_state` JSONB; cold-start applied |

### sitemap_harvester

| anomaly_type | severity | Signals |
|--------------|----------|---------|
| `sitemap_raw_empty` | warning | Sitemap fetch returned zero URLs when prior harvest metadata exists |
| `sitemap_reject_sample` | warning | Large sitemap sample classified as non-product (`reject_sample` mode) |
| `sitemap_useful_false` | info | Repeated non-useful sitemap harvests (streak ≥ 3) |

### category_processor

| anomaly_type | severity | Signals |
|--------------|----------|---------|
| `phase2_zero_yield` | warning | Phase 2 harvest processed categories but saved zero products |
| `phase2_converged_empty` | info | Consecutive empty category pages (convergence streak) |
| *(via helper)* `fetch_empty_soup_spike` | warning | High empty-soup fetch rate in `category_harvest` phase — see **fetch_adapter** |

### bfs_walker

| anomaly_type | severity | Signals |
|--------------|----------|---------|
| `phase1_budget_exhausted_no_publish` | warning | Phase 1 budget exhausted with queue remaining but no listings published |
| `phase1_repeated_exhausted` | info | Repeated phase-1 budget exhaustion (streak ≥ 3) |
| *(via helper)* `fetch_empty_soup_spike` | warning | High empty-soup fetch rate in `category_bfs` phase — see **fetch_adapter** |

### fetch_adapter

| anomaly_type | severity | Signals |
|--------------|----------|---------|
| `fetch_empty_soup_spike` | warning | ≥80% of fetches returned empty soup (≥5 samples) in a discovery phase |

Emitted from phase loops (`bfs_walker`, `category_processor`) via
`emit_fetch_empty_soup_spike_if_needed`; `fetch_adapter.py` stays stateless.

### url_canonicalizer

| anomaly_type | severity | Signals |
|--------------|----------|---------|
| `dedup_lookup_failed` | error | `load_existing_url_hashes` failed; save proceeds with empty pre-check set |
| `canonical_missing_rate_high` | info | ≥90% of soup-classified gate pages lack `<link rel=canonical>` (≥10 samples) |

### classifier_adapter

| anomaly_type | severity | Signals |
|--------------|----------|---------|
| `classify_unknown_rate_high` | warning | ≥70% structural role `unknown` on soup-classified pages (≥10 samples); **not** emitted in `reject_sample` mode |

---

## Grep source of truth (submodule | anomaly_type | severity)

```
budget_governor     | resume_index_desync              | warning
orchestrator        | meta_snapshot_write_failed       | critical
orchestrator        | discover_status_inconsistent     | warning
orchestrator        | discover_exception               | error
orchestrator        | finalize_write_rejected          | error
gate_persist        | pool_batch_commit_failed         | error
gate_persist        | pool_batch_total_reject          | warning
url_canonicalizer   | dedup_lookup_failed              | error
url_canonicalizer   | canonical_missing_rate_high      | info
classifier_adapter  | classify_unknown_rate_high       | warning
cursor_store        | resume_index_oob                 | warning
cursor_store        | frontier_deserialize_failed      | warning
sitemap_harvester   | sitemap_raw_empty                | warning
sitemap_harvester   | sitemap_reject_sample            | warning
sitemap_harvester   | sitemap_useful_false             | info
category_processor  | phase2_zero_yield                | warning
category_processor  | phase2_converged_empty           | info
fetch_adapter       | fetch_empty_soup_spike           | warning
bfs_walker          | phase1_budget_exhausted_no_publish | warning
bfs_walker          | phase1_repeated_exhausted        | info
```

All rows use `module = "discovery"`. Helpers in `alerting.py` route through
`emit_discovery_service_alert` with the submodule shown above.
