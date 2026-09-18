//! Imperecta data-ops — standalone Rust read-path service (slice R1).
//!
//! Serves the P6 cross-shop price-comparison contract straight off the
//! match groups written by the Python matching tick:
//!   GET /health
//!   GET /v1/groups/{group_id}/offers          (JWT)
//!   GET /v1/listings/{listing_id}/comparison  (JWT)
//!
//! Read-only by design: the data_firewall gate governs writes; reads are
//! plain operational SELECTs on indexed keys (ix_product_match_group,
//! idx_listing_url_hash-family). Auth mirrors the FastAPI backend: HS256
//! bearer tokens signed with the shared JWT_SECRET.

use std::{env, net::SocketAddr, sync::Arc, time::Duration};

use axum::{
    extract::{Path, State},
    http::{header, HeaderMap, Method, StatusCode},
    response::{IntoResponse, Response},
    routing::get,
    Json, Router,
};
use jsonwebtoken::{decode, Algorithm, DecodingKey, Validation};
use serde::{Deserialize, Serialize};
use serde_json::json;
use sqlx::{postgres::PgPoolOptions, PgPool, Row};
use tower_http::cors::{AllowOrigin, CorsLayer};
use uuid::Uuid;

#[derive(Clone)]
struct AppState {
    pool: PgPool,
    jwt_secret: Arc<String>,
}

#[derive(Debug, Deserialize)]
struct Claims {
    #[allow(dead_code)]
    sub: String,
    #[allow(dead_code)]
    exp: usize,
}

#[derive(Debug, Serialize)]
struct Offer {
    listing_id: Uuid,
    product_id: Uuid,
    marketplace_code: String,
    marketplace_name: String,
    country_code: String,
    name: String,
    title_en: Option<String>,
    external_url: String,
    last_price: Option<f64>,
    last_currency_code: Option<String>,
    last_price_eur: Option<f64>,
    last_checked_at: Option<chrono::DateTime<chrono::Utc>>,
    match_method: Option<String>,
    match_confidence: Option<f64>,
}

#[derive(Debug, Serialize)]
struct GroupOffers {
    group_id: Uuid,
    offers: Vec<Offer>,
    shops: usize,
    min_price_eur: Option<f64>,
    max_price_eur: Option<f64>,
}

enum ApiError {
    Unauthorized(&'static str),
    NotFound(&'static str),
    Internal(String),
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let (status, detail) = match self {
            ApiError::Unauthorized(d) => (StatusCode::UNAUTHORIZED, d.to_string()),
            ApiError::NotFound(d) => (StatusCode::NOT_FOUND, d.to_string()),
            ApiError::Internal(d) => {
                tracing::error!(error = %d, "internal error");
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    "internal error".to_string(),
                )
            }
        };
        (status, Json(json!({ "detail": detail }))).into_response()
    }
}

impl From<sqlx::Error> for ApiError {
    fn from(e: sqlx::Error) -> Self {
        ApiError::Internal(e.to_string())
    }
}

fn require_jwt(state: &AppState, headers: &HeaderMap) -> Result<Claims, ApiError> {
    let raw = headers
        .get(header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .ok_or(ApiError::Unauthorized("missing bearer token"))?;
    let mut validation = Validation::new(Algorithm::HS256);
    validation.validate_exp = true;
    decode::<Claims>(
        raw,
        &DecodingKey::from_secret(state.jwt_secret.as_bytes()),
        &validation,
    )
    .map(|data| data.claims)
    .map_err(|_| ApiError::Unauthorized("invalid token"))
}

const OFFERS_SQL: &str = r#"
SELECT fl.id AS listing_id,
       dp.id AS product_id,
       m.marketplace_code,
       m.name AS marketplace_name,
       m.country_code,
       dp.name,
       dp.title_en,
       fl.external_url,
       fl.last_price::float8 AS last_price,
       fl.last_currency_code,
       fl.last_price_eur::float8 AS last_price_eur,
       fl.last_checked_at,
       dp.match_method,
       dp.match_confidence::float8 AS match_confidence
FROM dim_product dp
JOIN fact_listing fl ON fl.product_id = dp.id AND fl.is_active
JOIN dim_marketplace m ON m.id = fl.marketplace_id
WHERE dp.match_group_id = $1 AND dp.is_active
ORDER BY fl.last_price_eur ASC NULLS LAST, m.marketplace_code ASC
LIMIT 200
"#;

async fn fetch_group_offers(pool: &PgPool, group_id: Uuid) -> Result<GroupOffers, ApiError> {
    let rows = sqlx::query(OFFERS_SQL).bind(group_id).fetch_all(pool).await?;
    let offers: Vec<Offer> = rows
        .iter()
        .map(|r| Offer {
            listing_id: r.get("listing_id"),
            product_id: r.get("product_id"),
            marketplace_code: r.get("marketplace_code"),
            marketplace_name: r.get("marketplace_name"),
            country_code: r.get("country_code"),
            name: r.get("name"),
            title_en: r.get("title_en"),
            external_url: r.get("external_url"),
            last_price: r.get("last_price"),
            last_currency_code: r.get("last_currency_code"),
            last_price_eur: r.get("last_price_eur"),
            last_checked_at: r.get("last_checked_at"),
            match_method: r.get("match_method"),
            match_confidence: r.get("match_confidence"),
        })
        .collect();
    let mut shops: Vec<&str> = offers.iter().map(|o| o.marketplace_code.as_str()).collect();
    shops.sort_unstable();
    shops.dedup();
    let prices: Vec<f64> = offers.iter().filter_map(|o| o.last_price_eur).collect();
    Ok(GroupOffers {
        group_id,
        shops: shops.len(),
        min_price_eur: prices.iter().cloned().fold(None, |acc: Option<f64>, p| {
            Some(acc.map_or(p, |a| a.min(p)))
        }),
        max_price_eur: prices.iter().cloned().fold(None, |acc: Option<f64>, p| {
            Some(acc.map_or(p, |a| a.max(p)))
        }),
        offers,
    })
}

async fn group_offers(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(group_id): Path<Uuid>,
) -> Result<Json<GroupOffers>, ApiError> {
    require_jwt(&state, &headers)?;
    let payload = fetch_group_offers(&state.pool, group_id).await?;
    if payload.offers.is_empty() {
        return Err(ApiError::NotFound("group not found or empty"));
    }
    Ok(Json(payload))
}

async fn listing_comparison(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(listing_id): Path<Uuid>,
) -> Result<Json<serde_json::Value>, ApiError> {
    require_jwt(&state, &headers)?;
    let row = sqlx::query(
        r#"
        SELECT dp.match_group_id, dp.match_method
        FROM fact_listing fl
        JOIN dim_product dp ON dp.id = fl.product_id
        WHERE fl.id = $1
        "#,
    )
    .bind(listing_id)
    .fetch_optional(&state.pool)
    .await?
    .ok_or(ApiError::NotFound("listing not found"))?;

    let group_id: Option<Uuid> = row.get("match_group_id");
    let method: Option<String> = row.get("match_method");
    match group_id {
        None => Ok(Json(json!({
            "listing_id": listing_id,
            "match_method": method,
            "group": null,
        }))),
        Some(gid) => {
            let payload = fetch_group_offers(&state.pool, gid).await?;
            Ok(Json(json!({
                "listing_id": listing_id,
                "match_method": method,
                "group": payload,
            })))
        }
    }
}

async fn health(State(state): State<AppState>) -> impl IntoResponse {
    let db_ok = sqlx::query("SELECT 1")
        .fetch_one(&state.pool)
        .await
        .is_ok();
    let status = if db_ok { StatusCode::OK } else { StatusCode::SERVICE_UNAVAILABLE };
    (status, Json(json!({ "status": if db_ok { "ok" } else { "degraded" }, "db": db_ok })))
}

fn normalize_db_url(raw: &str) -> String {
    // Accept SQLAlchemy-style URLs from shared env (postgresql+asyncpg://...).
    raw.replacen("postgresql+asyncpg://", "postgresql://", 1)
        .replacen("postgres+asyncpg://", "postgresql://", 1)
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "info".into()),
        )
        .init();

    let db_url = normalize_db_url(
        &env::var("DATABASE_URL").expect("DATABASE_URL is required"),
    );
    let jwt_secret = env::var("JWT_SECRET").expect("JWT_SECRET is required");
    let port: u16 = env::var("PORT").ok().and_then(|p| p.parse().ok()).unwrap_or(8090);

    let pool = PgPoolOptions::new()
        .max_connections(
            env::var("DATA_OPS_POOL_SIZE")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(5),
        )
        .acquire_timeout(Duration::from_secs(10))
        .connect(&db_url)
        .await
        .expect("database connection failed");

    let cors = CorsLayer::new()
        .allow_origin(AllowOrigin::predicate(|origin, _| {
            origin
                .to_str()
                .map(|o| {
                    o == "https://imperecta.pages.dev"
                        || o.starts_with("http://localhost")
                        || o.starts_with("http://127.0.0.1")
                })
                .unwrap_or(false)
        }))
        .allow_methods([Method::GET])
        .allow_headers([header::AUTHORIZATION, header::CONTENT_TYPE]);

    let app = Router::new()
        .route("/health", get(health))
        .route("/v1/groups/:group_id/offers", get(group_offers))
        .route("/v1/listings/:listing_id/comparison", get(listing_comparison))
        .layer(cors)
        .with_state(AppState {
            pool,
            jwt_secret: Arc::new(jwt_secret),
        });

    let addr = SocketAddr::from(([0, 0, 0, 0], port));
    tracing::info!(%addr, "data-ops listening");
    let listener = tokio::net::TcpListener::bind(addr).await.expect("bind failed");
    axum::serve(listener, app)
        .with_graceful_shutdown(async {
            let _ = tokio::signal::ctrl_c().await;
        })
        .await
        .expect("server error");
}

#[cfg(test)]
mod tests {
    use super::normalize_db_url;

    #[test]
    fn sqlalchemy_url_normalized() {
        assert_eq!(
            normalize_db_url("postgresql+asyncpg://u:p@h:5432/db"),
            "postgresql://u:p@h:5432/db"
        );
        assert_eq!(
            normalize_db_url("postgresql://u:p@h/db"),
            "postgresql://u:p@h/db"
        );
    }
}
