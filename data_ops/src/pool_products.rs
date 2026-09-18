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

use axum::{
    extract::{Query, State},
    http::HeaderMap,
    Json,
};
use base64::Engine as _;
use serde::Deserialize;
use serde_json::{json, Value};
use sqlx::{postgres::PgRow, Row};
use uuid::Uuid;

use crate::{require_jwt, ApiError, AppState};

const SEARCH_PRODUCT_CAP: usize = 1_500;
const SEARCH_LISTING_CAP: i64 = 4_000;
const COUNT_CAP: i64 = 10_001;

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
fn keyset_where(
    spec: &SortSpec,
    cur: &CursorPayload,
    args: &mut Vec<String>,
) -> String {
    let col = spec.key_expr;
    // Forward = continue in the sort's own direction; backwards inverts.
    let forward = !cur.backwards;
    let after_op = if spec.desc == forward { "<" } else { ">" };
    let id_op = if forward { ">" } else { "<" };
    match &cur.value {
        Some(v) => {
            args.push(v.clone());
            let n = args.len() + 3; // first 3 binds are reserved (see caller)
            let cast = spec.bind_cast;
            if forward {
                // values first, NULL block after
                format!(
                    "(({col} {after_op} ${n}{cast}) OR ({col} = ${n}{cast} AND fl.id {id_op} ${id}) OR ({col} IS NULL))",
                    id = n + 1
                )
            } else {
                format!(
                    "(({col} {after_op} ${n}{cast}) OR ({col} = ${n}{cast} AND fl.id {id_op} ${id}))",
                    id = n + 1
                )
            }
        }
        None => {
            args.push(String::new()); // placeholder, unused bind kept for shape
            let n = args.len() + 3;
            if forward {
                format!("(({col} IS NULL) AND fl.id {id_op} ${id})", id = n + 1)
            } else {
                // going back from the NULL tail: either earlier NULLs or any value
                format!(
                    "((({col} IS NULL) AND fl.id {id_op} ${id}) OR ({col} IS NOT NULL))",
                    id = n + 1
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
       sp.points AS recent_prices,
       CAST(NULL AS text) AS keyset_dummy
"#;

const ITEM_FROM: &str = r#"
FROM fact_listing fl
JOIN dim_product dp ON dp.id = fl.product_id
JOIN dim_marketplace m ON m.id = fl.marketplace_id
LEFT JOIN dim_brand b ON b.id = dp.brand_id
LEFT JOIN dim_category c ON c.id = dp.category_id
LEFT JOIN LATERAL (
    SELECT jsonb_agg(jsonb_build_object(
               'date', to_char(p.scraped_at, 'YYYY-MM-DD'),
               'price', p.price::float8,
               'currency', p.currency_code
           ) ORDER BY p.scraped_at ASC) AS points
    FROM (
        SELECT fp.scraped_at, fp.price, fp.currency_code
        FROM fact_price fp
        WHERE fp.listing_id = fl.id
        ORDER BY fp.scraped_at DESC
        LIMIT 8
    ) p
) sp ON true
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
    let recent: Option<Value> = r.get("recent_prices");
    json!({
        "id": r.get::<Uuid, _>("id"),
        "product_id": r.get::<Uuid, _>("product_id"),
        "title": r.get::<Option<String>, _>("title"),
        "image_url": r.get::<Option<String>, _>("image_url"),
        "url": r.get::<Option<String>, _>("url"),
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
    headers: HeaderMap,
    Query(params): Query<PoolParams>,
) -> Result<Json<Value>, ApiError> {
    require_jwt(&state, &headers)?;
    let pool = &state.pool;
    let limit = params.limit.unwrap_or(20).clamp(1, 500);
    let offset = params.offset.unwrap_or(0).max(0);
    let display_currency = params
        .display_currency
        .as_deref()
        .unwrap_or("local")
        .to_string();
    let spec = sort_spec(&params.sort);

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

    // --- WHERE assembly ($1 listing-ids, $2 marketplace, $3 category) ----
    let mut wheres: Vec<String> = vec!["fl.is_active".into(), "dp.is_active".into()];
    wheres.push("($1::uuid[] IS NULL OR fl.id = ANY($1))".into());
    wheres.push("($2::uuid IS NULL OR fl.marketplace_id = $2)".into());
    wheres.push(
        "($3::text IS NULL OR c.name ILIKE $3 OR c.name_en ILIKE $3 OR m.domain ILIKE $3)"
            .into(),
    );

    let cursor = params
        .cursor
        .as_deref()
        .filter(|_| spec.keyset)
        .and_then(decode_cursor);
    let mut extra_args: Vec<String> = Vec::new();
    let backwards = cursor.as_ref().map(|c| c.backwards).unwrap_or(false);
    if let Some(cur) = &cursor {
        wheres.push(keyset_where(&spec, cur, &mut extra_args));
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

    let mut query = sqlx::query(&sql)
        .bind(&search_listing_ids)
        .bind(params.marketplace_id)
        .bind(params.category.as_ref().map(|c| format!("%{c}%")));
    for (i, arg) in extra_args.iter().enumerate() {
        // bind 4.. : keyset value (text-comparable) then cursor id
        if cursor.as_ref().and_then(|c| c.value.as_ref()).is_some() || !arg.is_empty()
        {
            query = query.bind(arg.clone());
        } else {
            query = query.bind(Option::<String>::None);
        }
        if i == extra_args.len() - 1 {
            query = query.bind(cursor.as_ref().map(|c| c.id));
        }
    }
    let rows = query.fetch_all(pool).await?;
    let mut items: Vec<Value> = rows
        .iter()
        .map(|r| row_to_item(r, &display_currency))
        .collect();
    if backwards {
        items.reverse();
    }

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
            let count_sql = format!(
                "SELECT count(*) AS t FROM (SELECT fl.id {ITEM_FROM} WHERE {} LIMIT {COUNT_CAP}) s",
                wheres[..5].join(" AND ")
            );
            let row = sqlx::query(&count_sql)
                .bind(&search_listing_ids)
                .bind(params.marketplace_id)
                .bind(params.category.as_ref().map(|c| format!("%{c}%")))
                .fetch_one(pool)
                .await?;
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
