//! R4: the /pool/products grid read-path in Rust — contract-parity port of
//! the FastAPI endpoint (same params, same envelope, interchangeable
//! keyset cursors) so the frontend can switch the Products page over with
//! a base-URL change.
//!
//! Scope notes vs the Python original:
//! - display_currency: "local" (passthrough) and "EUR" (price_eur) are
//!   served; "USD" falls back to local (documented in the P6 spec).
//! - recent_prices sparkline: LEFT JOIN LATERAL, last 8 points per row.
//! - search: the in-memory index (search_index.rs) supplies product ids
//!   when warm; the SQL ILIKE phase is the cold fallback.

use std::{
    collections::HashMap,
    sync::{Arc, Mutex},
    time::{Duration, Instant},
};

use axum::{
    extract::{Query, State},
    Json,
};
use base64::Engine as _;
use serde::Deserialize;
use serde_json::{json, Value};
use sqlx::{postgres::PgRow, Row};
use uuid::Uuid;

use crate::{ApiError, AppState};

const SEARCH_PRODUCT_CAP: usize = 500;
const SEARCH_LISTING_CAP: i64 = 1_500;
const COUNT_CAP: i64 = 10_001;

/// Pool read limits (legal clean-up WP2, counsel §2.2/§3.8-3.9) — the same
/// env names as the FastAPI Settings so both read paths enforce one policy.
#[derive(Clone, Copy, Debug)]
pub struct PoolLimits {
    pub page_size_max: i64,
    pub page_depth_max: i64,
    pub rate_limit_per_hour: u32,
    pub max_per_source_unfiltered: usize,
    pub browse_scan_cap: i64,
    pub browse_cache_sec: u64,
}

impl PoolLimits {
    pub fn from_env() -> Self {
        fn env_or<T: std::str::FromStr>(name: &str, default: T) -> T {
            std::env::var(name).ok().and_then(|v| v.parse().ok()).unwrap_or(default)
        }
        Self {
            page_size_max: env_or("POOL_PAGE_SIZE_MAX", 50),
            page_depth_max: env_or("POOL_PAGE_DEPTH_MAX", 10),
            rate_limit_per_hour: env_or("POOL_RATE_LIMIT_PER_HOUR", 600),
            max_per_source_unfiltered: env_or("POOL_MAX_PER_SOURCE_UNFILTERED", 20),
            browse_scan_cap: env_or("POOL_BROWSE_SCAN_CAP", 50_000),
            browse_cache_sec: env_or("POOL_BROWSE_CACHE_SEC", 60),
        }
    }

    /// Deepest page start: page_depth_max pages of page_size_max rows.
    pub fn offset_max(&self) -> i64 {
        self.page_size_max * (self.page_depth_max - 1)
    }

    pub fn browse_depth(&self) -> usize {
        (self.page_size_max * self.page_depth_max) as usize
    }
}

/// Keep the ordered prefix of `rows` = (listing_id, marketplace_id) with at
/// most `per_source` rows per marketplace and `depth` rows in total — one
/// pass, one counter per marketplace (the twin of
/// `product_pool.service.cap_per_source`, same test vectors).
pub fn cap_per_source(rows: &[(Uuid, Uuid)], per_source: usize, depth: usize) -> Vec<Uuid> {
    let mut seen: HashMap<Uuid, usize> = HashMap::new();
    let mut kept = Vec::with_capacity(depth.min(rows.len()));
    for (listing_id, marketplace_id) in rows {
        let n = seen.entry(*marketplace_id).or_insert(0);
        if *n >= per_source {
            continue;
        }
        *n += 1;
        kept.push(*listing_id);
        if kept.len() >= depth {
            break;
        }
    }
    kept
}

/// The unfiltered browse set per sort, shared by every viewer for
/// `browse_cache_sec` (one narrow scan per sort per minute, not per request).
#[derive(Default)]
pub struct BrowseCache {
    sets: Mutex<HashMap<String, (Instant, Arc<Vec<Uuid>>)>>,
}

impl BrowseCache {
    fn get(&self, sort: &str, ttl: Duration) -> Option<Arc<Vec<Uuid>>> {
        let sets = self.sets.lock().ok()?;
        sets.get(sort)
            .filter(|(at, _)| at.elapsed() < ttl)
            .map(|(_, ids)| ids.clone())
    }

    fn put(&self, sort: &str, ids: Vec<Uuid>) -> Arc<Vec<Uuid>> {
        let ids = Arc::new(ids);
        if let Ok(mut sets) = self.sets.lock() {
            sets.insert(sort.to_string(), (Instant::now(), ids.clone()));
        }
        ids
    }
}

#[derive(Debug, Deserialize)]
pub struct PoolParams {
    pub search: Option<String>,
    pub marketplace_id: Option<Uuid>,
    pub category: Option<String>,
    #[serde(default = "default_sort")]
    pub sort: String,
    pub limit: Option<i64>,
    pub offset: Option<i64>,
    pub cursor: Option<String>,
    #[serde(default)]
    pub skip_total: bool,
    pub display_currency: Option<String>,
}

fn default_sort() -> String {
    "recent".to_string()
}

struct SortSpec {
    /// SQL expression for the sort key (also the keyset column).
    key_expr: &'static str,
    /// Cast applied to the (text) keyset bind so Postgres compares typed.
    bind_cast: &'static str,
    desc: bool,
    /// Keyset-capable (recent/name/price); pct sorts stay on offset.
    keyset: bool,
}

fn sort_spec(sort: &str) -> SortSpec {
    match sort {
        "name_asc" => SortSpec { key_expr: "dp.name", bind_cast: "::text", desc: false, keyset: true },
        "name_desc" => SortSpec { key_expr: "dp.name", bind_cast: "::text", desc: true, keyset: true },
        "price_asc" => SortSpec { key_expr: "fl.last_price", bind_cast: "::numeric", desc: false, keyset: true },
        "price_desc" => SortSpec { key_expr: "fl.last_price", bind_cast: "::numeric", desc: true, keyset: true },
        "gainers" => SortSpec { key_expr: "fl.last_price_change_pct", bind_cast: "", desc: true, keyset: false },
        "losers" => SortSpec { key_expr: "fl.last_price_change_pct", bind_cast: "", desc: false, keyset: false },
        "volatile" => SortSpec { key_expr: "abs(fl.last_price_change_pct)", bind_cast: "", desc: true, keyset: false },
        // recent | trending | anything else
        _ => SortSpec { key_expr: "fl.last_checked_at", bind_cast: "::timestamptz", desc: true, keyset: true },
    }
}

#[derive(Debug)]
struct CursorPayload {
    backwards: bool,
    value: Option<String>,
    id: Uuid,
}

fn decode_cursor(raw: &str) -> Option<CursorPayload> {
    let padded = {
        let mut s = raw.to_string();
        while s.len() % 4 != 0 {
            s.push('=');
        }
        s
    };
    let bytes = base64::engine::general_purpose::URL_SAFE.decode(padded).ok()?;
    let v: Value = serde_json::from_slice(&bytes).ok()?;
    let id = v.get("id")?.as_str()?.parse().ok()?;
    let value = match v.get("v") {
        None | Some(Value::Null) => None,
        Some(Value::String(s)) => Some(s.clone()),
        Some(other) => Some(other.to_string()),
    };
    Some(CursorPayload {
        backwards: v.get("d").and_then(|d| d.as_str()) == Some("prev"),
        value,
        id,
    })
}

fn encode_cursor(direction: &str, value: &Option<String>, id: &Uuid) -> String {
    let payload = json!({
        "d": direction,
        "v": value,
        "id": id.to_string(),
    });
    base64::engine::general_purpose::URL_SAFE
        .encode(payload.to_string())
        .trim_end_matches('=')
        .to_string()
}

/// Keyset predicate with NULLS LAST semantics on both directions.
/// `value_bind`/`id_bind` are the 1-based bind positions assigned by the
/// caller (value bind is absent for NULL-valued cursors).
fn keyset_where(
    spec: &SortSpec,
    cur: &CursorPayload,
    value_bind: Option<usize>,
    id_bind: usize,
) -> String {
    let col = spec.key_expr;
    // Forward = continue in the sort's own direction; backwards inverts.
    let forward = !cur.backwards;
    let after_op = if spec.desc == forward { "<" } else { ">" };
    let id_op = if forward { ">" } else { "<" };
    match value_bind {
        Some(n) => {
            let cast = spec.bind_cast;
            if forward {
                // values first, NULL block after
                format!(
                    "(({col} {after_op} ${n}{cast}) OR ({col} = ${n}{cast} AND fl.id {id_op} ${id_bind}) OR ({col} IS NULL))"
                )
            } else {
                format!(
                    "(({col} {after_op} ${n}{cast}) OR ({col} = ${n}{cast} AND fl.id {id_op} ${id_bind}))"
                )
            }
        }
        None => {
            if forward {
                format!("(({col} IS NULL) AND fl.id {id_op} ${id_bind})")
            } else {
                // going back from the NULL tail: earlier NULLs or any value
                format!(
                    "((({col} IS NULL) AND fl.id {id_op} ${id_bind}) OR ({col} IS NOT NULL))"
                )
            }
        }
    }
}

const ITEM_SELECT: &str = r#"
SELECT fl.id,
       dp.id AS product_id,
       dp.name AS title,
       dp.image_url,
       fl.external_url AS url,
       m.id AS marketplace_id,
       m.name AS marketplace_name,
       m.domain AS marketplace_domain,
       m.marketplace_code,
       m.country_code,
       b.name AS brand,
       c.name AS category,
       dp.product_type,
       dp.product_type_en,
       c.name_en AS category_en,
       dp.title_en,
       fl.last_price::float8 AS price,
       fl.last_currency_code AS currency,
       fl.last_price_eur::float8 AS price_eur,
       fl.last_price_change_pct::float8 AS price_change_pct,
       fl.last_checked_at,
       fl.is_active,
       dp.match_group_id,
       dp.match_method,
       CAST(NULL AS text) AS keyset_dummy
"#;

const ITEM_FROM: &str = r#"
FROM fact_listing fl
JOIN dim_product dp ON dp.id = fl.product_id
JOIN dim_marketplace m ON m.id = fl.marketplace_id
LEFT JOIN dim_brand b ON b.id = dp.brand_id
LEFT JOIN dim_category c ON c.id = dp.category_id
"#;

/// Sparklines for exactly the page's listings — the Python endpoint does
/// the same second-query pattern: a LATERAL inside the top-N page query
/// was observed to defeat the planner's early stop on the 2.4M table.
const SPARKLINE_SQL: &str = r#"
SELECT l.id AS listing_id,
       (SELECT jsonb_agg(jsonb_build_object(
                   'date', to_char(p.scraped_at, 'YYYY-MM-DD'),
                   'price', p.price::float8,
                   'currency', p.currency_code
               ) ORDER BY p.scraped_at ASC)
        FROM (
            SELECT fp.scraped_at, fp.price, fp.currency_code
            FROM fact_price fp
            WHERE fp.listing_id = l.id
            ORDER BY fp.scraped_at DESC
            LIMIT 8
        ) p) AS points
FROM unnest($1::uuid[]) AS l(id)
"#;

fn row_to_item(r: &PgRow, display_currency: &str) -> Value {
    let price: Option<f64> = r.get("price");
    let price_eur: Option<f64> = r.get("price_eur");
    let currency: Option<String> = r.get("currency");
    let (display_price, display_curr, conv) = match display_currency {
        "EUR" => (price_eur, Some("EUR".to_string()), price_eur.is_some()),
        _ => (price, currency.clone(), price.is_some()),
    };
    let last_checked: Option<chrono::DateTime<chrono::Utc>> = r.get("last_checked_at");
    let recent: Option<Value> = None;
    json!({
        "id": r.get::<Uuid, _>("id"),
        "product_id": r.get::<Uuid, _>("product_id"),
        "title": r.get::<Option<String>, _>("title"),
        "image_url": r.get::<Option<String>, _>("image_url"),
        "url": r.get::<Option<String>, _>("url"),
        // Source attribution (counsel §3.9): origin listing + host on every card.
        "external_url": r.get::<Option<String>, _>("url"),
        "source_domain": r.get::<Option<String>, _>("marketplace_domain"),
        "marketplace_id": r.get::<Option<Uuid>, _>("marketplace_id"),
        "marketplace_name": r.get::<Option<String>, _>("marketplace_name"),
        "marketplace_domain": r.get::<Option<String>, _>("marketplace_domain"),
        "marketplace_code": r.get::<Option<String>, _>("marketplace_code"),
        "country_code": r.get::<Option<String>, _>("country_code"),
        "brand": r.get::<Option<String>, _>("brand"),
        "category": r.get::<Option<String>, _>("category"),
        "product_type": r.get::<Option<String>, _>("product_type"),
        "product_type_en": r.get::<Option<String>, _>("product_type_en"),
        "category_en": r.get::<Option<String>, _>("category_en"),
        "title_en": r.get::<Option<String>, _>("title_en"),
        "price": price,
        "currency": currency,
        "price_eur": price_eur,
        "display_price": display_price,
        "display_currency": display_curr,
        "conversion_available": conv,
        "local_currency_resolution": Value::Null,
        "local_currency_unavailable": false,
        "price_change_pct": r.get::<Option<f64>, _>("price_change_pct"),
        "last_checked_at": last_checked,
        "status": Value::Null,
        "is_active": r.get::<Option<bool>, _>("is_active"),
        "match_group_id": r.get::<Option<Uuid>, _>("match_group_id"),
        "match_method": r.get::<Option<String>, _>("match_method"),
        "recent_prices": recent.unwrap_or_else(|| json!([])),
    })
}

/// Sparklines for the page (second bounded query, python-parity).
async fn attach_sparklines(pool: &sqlx::PgPool, items: &mut [Value]) {
    if items.is_empty() {
        return;
    }
    let page_ids: Vec<Uuid> = items
        .iter()
        .filter_map(|i| i["id"].as_str().and_then(|s| s.parse().ok()))
        .collect();
    if let Ok(spark_rows) = sqlx::query(SPARKLINE_SQL)
        .bind(&page_ids)
        .fetch_all(pool)
        .await
    {
        use std::collections::HashMap;
        let mut by_id: HashMap<Uuid, Value> = HashMap::new();
        for r in &spark_rows {
            let id: Uuid = r.get("listing_id");
            let points: Option<Value> = r.get("points");
            by_id.insert(id, points.unwrap_or_else(|| json!([])));
        }
        for item in items.iter_mut() {
            if let Some(id) = item["id"].as_str().and_then(|s| s.parse::<Uuid>().ok()) {
                item["recent_prices"] = by_id.remove(&id).unwrap_or_else(|| json!([]));
            }
        }
    }
}

/// Live catch-up for the rows a viewer already has on screen: the edge
/// serves a ≤5-minute-old page instantly, then the page asks for exactly
/// its listing ids and swaps in current prices. PK lookup, ≤500 ids —
/// never cached (POST).
pub const REFRESH_MAX_IDS: usize = 500;

#[derive(Debug, Deserialize)]
pub struct RefreshBody {
    pub ids: Vec<Uuid>,
    pub display_currency: Option<String>,
}

pub async fn pool_products_refresh(
    State(state): State<AppState>,
    Json(body): Json<RefreshBody>,
) -> Result<Json<Value>, ApiError> {
    if body.ids.len() > REFRESH_MAX_IDS {
        return Err(ApiError::BadRequest("too many ids (max 500)"));
    }
    let display_currency = body
        .display_currency
        .as_deref()
        .unwrap_or("local")
        .to_string();
    let mut items: Vec<Value> = Vec::new();
    if !body.ids.is_empty() {
        let sql = format!("{ITEM_SELECT}{ITEM_FROM}WHERE fl.id = ANY($1)");
        let rows = sqlx::query(&sql)
            .bind(&body.ids)
            .fetch_all(&state.pool)
            .await?;
        items = rows
            .iter()
            .map(|r| row_to_item(r, &display_currency))
            .collect();
        attach_sparklines(&state.pool, &mut items).await;
    }
    Ok(Json(json!({
        "items": items,
        "refreshed_at": chrono::Utc::now(),
    })))
}

fn keyset_value_of(item: &Value, sort: &str) -> Option<String> {
    let key = match sort {
        "name_asc" | "name_desc" => "title",
        "price_asc" | "price_desc" => "price",
        _ => "last_checked_at",
    };
    match item.get(key) {
        None | Some(Value::Null) => None,
        Some(Value::String(s)) => Some(s.clone()),
        Some(other) => Some(other.to_string()),
    }
}

pub async fn pool_products(
    State(state): State<AppState>,
    Query(params): Query<PoolParams>,
) -> Result<Json<Value>, ApiError> {
    let pool = &state.pool;
    let limits = state.limits;
    let limit = params.limit.unwrap_or(20).clamp(1, limits.page_size_max);
    let offset = params.offset.unwrap_or(0).clamp(0, limits.offset_max());
    let display_currency = params
        .display_currency
        .as_deref()
        .unwrap_or("local")
        .to_string();
    let spec = sort_spec(&params.sort);

    // --- unfiltered browsing: the shared per-source-capped set ------------
    let has_search = params.search.as_deref().map(str::trim).map_or(false, |q| q.len() >= 2);
    if !has_search && params.marketplace_id.is_none() && params.category.is_none() {
        return browse_page(&state, &spec, &params.sort, limit, offset, &display_currency).await;
    }

    // --- search phase: in-memory index when warm, SQL ILIKE fallback -----
    let mut search_listing_ids: Option<Vec<Uuid>> = None;
    let mut search_capped = false;
    if let Some(q) = params.search.as_deref().map(str::trim) {
        if q.len() >= 2 {
            let product_ids: Vec<Uuid> = match state.index.search(q, SEARCH_PRODUCT_CAP) {
                Some(hits) => {
                    search_capped = hits.len() >= SEARCH_PRODUCT_CAP;
                    hits
                }
                None => {
                    let like =
                        format!("%{}%", q.replace('%', "\\%").replace('_', "\\_"));
                    let rows = sqlx::query(
                        "SELECT id FROM dim_product WHERE name ILIKE $1 LIMIT 1500",
                    )
                    .bind(&like)
                    .fetch_all(pool)
                    .await?;
                    search_capped = rows.len() >= SEARCH_PRODUCT_CAP;
                    rows.iter().map(|r| r.get("id")).collect()
                }
            };
            if product_ids.is_empty() {
                return Ok(Json(empty_envelope(limit, offset)));
            }
            let rows = sqlx::query(
                "SELECT fl.id FROM fact_listing fl
                 WHERE fl.product_id = ANY($1) AND fl.is_active LIMIT $2",
            )
            .bind(&product_ids)
            .bind(SEARCH_LISTING_CAP)
            .fetch_all(pool)
            .await?;
            search_capped = search_capped || rows.len() as i64 >= SEARCH_LISTING_CAP;
            let ids: Vec<Uuid> = rows.iter().map(|r| r.get("id")).collect();
            if ids.is_empty() {
                return Ok(Json(empty_envelope(limit, offset)));
            }
            search_listing_ids = Some(ids);
        }
    }

    // --- WHERE assembly: conditional clauses only — a "$n IS NULL OR ..."
    // disjunction defeats partial-index proofs and generic plans on the
    // 2.17M-row table (observed 25s scans). Bind indices are sequential.
    let mut wheres: Vec<String> = vec!["fl.is_active".into()];
    let mut bind_no = 0usize;
    let ids_bind = search_listing_ids.as_ref().map(|_| {
        bind_no += 1;
        bind_no
    });
    if let Some(n) = ids_bind {
        wheres.push(format!("fl.id = ANY(${n})"));
    }
    let mp_bind = params.marketplace_id.map(|_| {
        bind_no += 1;
        bind_no
    });
    if let Some(n) = mp_bind {
        wheres.push(format!("fl.marketplace_id = ${n}"));
    }
    let cat_bind = params.category.as_ref().map(|_| {
        bind_no += 1;
        bind_no
    });
    if let Some(n) = cat_bind {
        wheres.push(format!(
            "(c.name ILIKE ${n} OR c.name_en ILIKE ${n} OR m.domain ILIKE ${n})"
        ));
    }

    let cursor = params
        .cursor
        .as_deref()
        .filter(|_| spec.keyset)
        .and_then(decode_cursor);
    let backwards = cursor.as_ref().map(|c| c.backwards).unwrap_or(false);
    let mut keyset_value_bind: Option<usize> = None;
    if let Some(cur) = &cursor {
        let vb = cur.value.as_ref().map(|_| {
            bind_no += 1;
            bind_no
        });
        keyset_value_bind = vb;
        bind_no += 1;
        let idb = bind_no;
        wheres.push(keyset_where(&spec, cur, vb, idb));
    }

    let base_dir = if spec.desc { "DESC" } else { "ASC" };
    let (eff_dir, eff_id_dir) = if backwards {
        (if spec.desc { "ASC" } else { "DESC" }, "DESC")
    } else {
        (base_dir, "ASC")
    };
    let order = format!(
        "ORDER BY {} {} NULLS {}, fl.id {}",
        spec.key_expr,
        eff_dir,
        if backwards { "FIRST" } else { "LAST" },
        eff_id_dir
    );

    let use_offset = cursor.is_none();
    let mut sql = format!(
        "{ITEM_SELECT} {ITEM_FROM} WHERE {} {} LIMIT {}",
        wheres.join(" AND "),
        order,
        limit
    );
    if use_offset {
        sql.push_str(&format!(" OFFSET {offset}"));
    }

    let mut query = sqlx::query(&sql);
    if let Some(ids) = &search_listing_ids {
        query = query.bind(ids);
    }
    if let Some(mp) = params.marketplace_id {
        query = query.bind(mp);
    }
    if let Some(cat) = &params.category {
        query = query.bind(format!("%{cat}%"));
    }
    if let Some(cur) = &cursor {
        if keyset_value_bind.is_some() {
            query = query.bind(cur.value.clone().unwrap_or_default());
        }
        query = query.bind(cur.id);
    }
    let rows = query.fetch_all(pool).await?;
    let mut items: Vec<Value> = rows
        .iter()
        .map(|r| row_to_item(r, &display_currency))
        .collect();
    if backwards {
        items.reverse();
    }

    attach_sparklines(pool, &mut items).await;

    // --- totals ----------------------------------------------------------
    let mut total: Option<i64> = None;
    let mut total_is_estimate = false;
    if !params.skip_total {
        let unfiltered = search_listing_ids.is_none()
            && params.marketplace_id.is_none()
            && params.category.is_none();
        if unfiltered {
            if let Ok(row) = sqlx::query(
                "SELECT total_listings::bigint AS t FROM mv_pool_stats LIMIT 1",
            )
            .fetch_one(pool)
            .await
            {
                total = Some(row.get("t"));
                total_is_estimate = true;
            }
        }
        if total.is_none() {
            // Count over the FILTER clauses only (index of the first keyset
            // clause == 2 base + number of present filters).
            let filter_clause_end = 1
                + ids_bind.map(|_| 1).unwrap_or(0)
                + mp_bind.map(|_| 1).unwrap_or(0)
                + cat_bind.map(|_| 1).unwrap_or(0);
            let count_sql = format!(
                "SELECT count(*) AS t FROM (SELECT fl.id {ITEM_FROM} WHERE {} LIMIT {COUNT_CAP}) s",
                wheres[..filter_clause_end].join(" AND ")
            );
            let mut cq = sqlx::query(&count_sql);
            if let Some(ids) = &search_listing_ids {
                cq = cq.bind(ids);
            }
            if let Some(mp) = params.marketplace_id {
                cq = cq.bind(mp);
            }
            if let Some(cat) = &params.category {
                cq = cq.bind(format!("%{cat}%"));
            }
            let row = cq.fetch_one(pool).await?;
            let t: i64 = row.get("t");
            total_is_estimate = t >= COUNT_CAP || search_capped;
            total = Some(t.min(COUNT_CAP - 1));
        }
    }

    // --- cursors ----------------------------------------------------------
    let (next_cursor, prev_cursor) = if spec.keyset && !items.is_empty() {
        let first = &items[0];
        let last = &items[items.len() - 1];
        let has_more = items.len() as i64 == limit;
        let next = if has_more || backwards {
            Some(encode_cursor(
                "next",
                &keyset_value_of(last, &params.sort),
                &last["id"].as_str().unwrap().parse().unwrap(),
            ))
        } else {
            None
        };
        let prev = if cursor.is_some() {
            Some(encode_cursor(
                "prev",
                &keyset_value_of(first, &params.sort),
                &first["id"].as_str().unwrap().parse().unwrap(),
            ))
        } else {
            None
        };
        (next, prev)
    } else {
        (None, None)
    };

    Ok(Json(json!({
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "total_is_estimate": total_is_estimate,
        "next_cursor": next_cursor,
        "prev_cursor": prev_cursor,
    })))
}

/// Unfiltered browsing (WP2): the first `browse_scan_cap` rows of the sort
/// order — ids only, index-driven — capped to `max_per_source_unfiltered`
/// per marketplace and `browse_depth` rows, cached per sort; the page is a
/// slice hydrated by primary key. Offset pagination only, no cursors.
async fn browse_page(
    state: &AppState,
    spec: &SortSpec,
    sort: &str,
    limit: i64,
    offset: i64,
    display_currency: &str,
) -> Result<Json<Value>, ApiError> {
    let limits = state.limits;
    let ttl = Duration::from_secs(limits.browse_cache_sec);
    let browse_ids = match state.browse.get(sort, ttl) {
        Some(ids) => ids,
        None => {
            let name_join = if spec.key_expr.starts_with("dp.") {
                "JOIN dim_product dp ON dp.id = fl.product_id"
            } else {
                ""
            };
            let scan_sql = format!(
                "SELECT fl.id, fl.marketplace_id FROM fact_listing fl {name_join} \
                 WHERE fl.is_active AND (fl.page_role = 'product' \
                       OR (fl.page_role IS NULL AND fl.last_price IS NOT NULL)) \
                 ORDER BY {} {} NULLS LAST, fl.id ASC LIMIT {}",
                spec.key_expr,
                if spec.desc { "DESC" } else { "ASC" },
                limits.browse_scan_cap
            );
            let rows = sqlx::query(&scan_sql).fetch_all(&state.pool).await?;
            let scanned: Vec<(Uuid, Uuid)> = rows
                .iter()
                .map(|r| (r.get::<Uuid, _>("id"), r.get::<Uuid, _>("marketplace_id")))
                .collect();
            let capped = cap_per_source(
                &scanned,
                limits.max_per_source_unfiltered,
                limits.browse_depth(),
            );
            state.browse.put(sort, capped)
        }
    };
    let start = (offset as usize).min(browse_ids.len());
    let end = (start + limit as usize).min(browse_ids.len());
    let page_ids: Vec<Uuid> = browse_ids[start..end].to_vec();
    let mut items: Vec<Value> = Vec::new();
    if !page_ids.is_empty() {
        let sql = format!("{ITEM_SELECT}{ITEM_FROM}WHERE fl.id = ANY($1)");
        let rows = sqlx::query(&sql).bind(&page_ids).fetch_all(&state.pool).await?;
        let mut by_id: HashMap<Uuid, Value> = rows
            .iter()
            .map(|r| (r.get::<Uuid, _>("id"), row_to_item(r, display_currency)))
            .collect();
        items = page_ids.iter().filter_map(|id| by_id.remove(id)).collect();
        attach_sparklines(&state.pool, &mut items).await;
    }
    Ok(Json(json!({
        "items": items,
        "total": browse_ids.len(),
        "limit": limit,
        "offset": offset,
        "total_is_estimate": false,
        "next_cursor": Value::Null,
        "prev_cursor": Value::Null,
    })))
}

fn empty_envelope(limit: i64, offset: i64) -> Value {
    json!({
        "items": [],
        "total": 0,
        "limit": limit,
        "offset": offset,
        "total_is_estimate": false,
        "next_cursor": Value::Null,
        "prev_cursor": Value::Null,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cursor_roundtrip_matches_python_shape() {
        let id: Uuid = "44eba3b6-65b8-4e01-91f1-38ec7d6b89d6".parse().unwrap();
        let enc = encode_cursor("next", &Some("2026-09-18T10:00:00".into()), &id);
        let dec = decode_cursor(&enc).unwrap();
        assert!(!dec.backwards);
        assert_eq!(dec.id, id);
        assert_eq!(dec.value.as_deref(), Some("2026-09-18T10:00:00"));
        // null value cursor
        let enc2 = encode_cursor("prev", &None, &id);
        let dec2 = decode_cursor(&enc2).unwrap();
        assert!(dec2.backwards);
        assert!(dec2.value.is_none());
    }

    fn uid(n: u128) -> Uuid {
        Uuid::from_u128(n)
    }

    #[test]
    fn cap_per_source_matches_the_python_vectors() {
        let (a, b, c) = (uid(1_000), uid(2_000), uid(3_000));
        let ids: Vec<Uuid> = (0..30).map(uid).collect();
        // 5 of a, then b, c, b, then a again
        let mut rows: Vec<(Uuid, Uuid)> = (0..5).map(|i| (ids[i], a)).collect();
        rows.extend([(ids[10], b), (ids[11], c), (ids[12], b), (ids[20], a)]);
        assert_eq!(
            cap_per_source(&rows, 2, 100),
            vec![ids[0], ids[1], ids[10], ids[11], ids[12]]
        );
        let rows2 = vec![(ids[0], a), (ids[1], b), (ids[2], a), (ids[3], b), (ids[4], a)];
        assert_eq!(cap_per_source(&rows2, 5, 3), vec![ids[0], ids[1], ids[2]]);
        assert!(cap_per_source(&[], 20, 500).is_empty());
    }

    #[test]
    fn limits_default_to_the_policy_values() {
        let l = PoolLimits {
            page_size_max: 50,
            page_depth_max: 10,
            rate_limit_per_hour: 600,
            max_per_source_unfiltered: 20,
            browse_scan_cap: 50_000,
            browse_cache_sec: 60,
        };
        assert_eq!(l.offset_max(), 450);
        assert_eq!(l.browse_depth(), 500);
    }

    #[test]
    fn sort_specs_cover_all_contract_sorts() {
        for s in [
            "recent", "trending", "name_asc", "name_desc", "price_asc",
            "price_desc", "gainers", "losers", "volatile",
        ] {
            let spec = sort_spec(s);
            assert!(!spec.key_expr.is_empty());
        }
        assert!(!sort_spec("gainers").keyset);
        assert!(sort_spec("recent").keyset);
    }
}
