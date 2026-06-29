# Gate Alert Registry

Single accumulating registry for gate and operational alert paths. Future seams
**append rows here** — do not create separate alert-spec files.

**Consumer endpoint:** `GET /api/admin/service_alerts` (`list_service_alerts` in
`backend/app/modules/admin/api_alerts.py`).

**Carve-outs (unsigned INSERT, bypass gate):**

| Store | Helper | Migration grant |
|-------|--------|-----------------|
| `reject_data` | `write_reject_data` / `write_reject_data_isolated` | 040 INSERT + RLS |
| `service_alerts` | `write_service_alert_isolated` | 045 INSERT (no RLS) |

---

## Registered alerts (seam 9.4-reroute)

| anomaly_type | class | module | submodule | severity | meaning |
|--------------|-------|--------|-----------|----------|---------|
| `gate_write_invalid_signature` | SERVICE | `data_firewall` | `persist_rpc` | warning | Python `verify()` passed but `gate.exec_write` / `exec_write_batch` rejected the HMAC — wire-build bug or tamper. Backup: `reject_data` row; controlled `PersistResult(ok=False)`. |
| `gate_write_signing_unavailable` | SERVICE | `data_firewall` | `persist_rpc` | critical | Vault signing secret missing in DB (`signing_unavailable`). Write outage; exception re-raised after alert. |
| `gate_write_rpc_error` | SERVICE | `data_firewall` | `persist_rpc` | error | Any other gate RPC failure (`unsupported_operation`, DB error, …). Exception re-raised after alert. |

---

## Deferred (registry only — later passes)

| item | notes |
|------|-------|
| Distinct SQLSTATEs for gate `RAISE` | Replace text-matching in Python handlers (9.2 function change). |
| pg_cron E1/E2 failure alerts | Cron-failure monitor in next defence-in-depth pass. |
