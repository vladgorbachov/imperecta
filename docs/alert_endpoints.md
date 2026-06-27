# Alert endpoint registry

Operational and analytic alert classes are **separate** (data-class separation). Every row in any alert table carries `alert_class` — no bare/unsigned alert may exist.

| Class | Table(s) | `alert_class` value |
|-------|----------|---------------------|
| Service (operational / health) | `service_alerts` | `service` |
| Analytic (client price-alerts) | `alerts`, `alert_events` | `analytic` |

## Endpoints

### `GET /api/admin/service_alerts`

| Field | Value |
|-------|-------|
| **Path** | `/api/admin/service_alerts` |
| **Auth** | Superuser only (`get_current_superuser`) |
| **Data class** | Service-data (no `user_id`) |
| **First node** | `discovery` / `budget_governor` |
| **Anomaly types (planned)** | `detector_divergence`, `resume_index_desync` (+ future nodes) |
| **Purpose** | Operational/health alerts for the admin panel; filter by `module`, `submodule`, `severity`, `resolved` |
| **Writer** | Artefact 3 (`budget_governor`) via `build_service_alert_fields` + gate persist — **not wired in artefact 2** |

Query filters: `module`, `submodule`, `severity`, `resolved` (`open` \| `resolved` \| `all`), `limit`, `offset`.

### `GET /api/admin/analytic_alerts`

| Field | Value |
|-------|-------|
| **Path** | `/api/admin/analytic_alerts` |
| **Auth** | Superuser only (`get_current_superuser`) |
| **Data class** | User-data (`alerts.user_id` NOT NULL) |
| **Source tables** | `alerts` + `alert_events` (thin read; no new feature) |
| **Purpose** | Admin read of client analytic price-alert events |
| **Writer** | Existing client alert pipeline (unchanged) |

Query filters: `alert_type`, `severity`, `user_id`, `limit`, `offset`.

## Class-signature invariant

- `service_alerts.alert_class` NOT NULL, server default `'service'`, CHECK `alert_class = 'service'`.
- `alerts.alert_class` NOT NULL, server default `'analytic'`.
- `alert_events.alert_class` NOT NULL, server default `'analytic'`.
- Migration `032_service_alerts_and_alert_class` applies DDL through the maintenance audit gate (`record_maintenance_audit` → `api_logs`).

## Gate-write (service alerts only)

Artefact 3 inserts via:

- `build_service_alert_fields(module, submodule, severity, anomaly_type, message, context=...)`
- `write_service_alert_sync` / `write_service_alert_async` → `evaluate_market` → `persist`
- Contract: `FACT_TABLE_CONTRACTS["service_alerts"]`, locator `id`, `TABLE_LOCATORS["service_alerts"] = ("id",)`
