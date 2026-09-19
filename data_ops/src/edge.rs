//! Edge-cache contract for the public read routes (stale-while-revalidate
//! architecture, 2026-09-19) — the Rust twin of
//! `backend/app/common/public_cache.py`.
//!
//! Every `/v1/*` response is identical for every anonymous viewer, so a
//! CDN in front of this service holds 5-minute snapshots and serves them
//! stale while it revalidates in the background. Rules:
//!
//! * anonymous GET 200 → `Cache-Control: public, s-maxage, swr` + weak
//!   `ETag`; a matching `If-None-Match` short-circuits to 304.
//! * a request carrying `Authorization` → `private, no-store` — never in
//!   the shared cache (the frontend sends no token on public reads).
//! * the live refresh call (`POST /v1/pool/products/refresh`) is never
//!   cached: it is the "catch up to now" half of the pattern.

use std::hash::{DefaultHasher, Hash, Hasher};

use axum::{
    body::{to_bytes, Body},
    extract::Request,
    http::{header, HeaderValue, Method, StatusCode},
    middleware::Next,
    response::Response,
};

pub const PUBLIC_S_MAXAGE_SEC: u32 = 300;
pub const PUBLIC_STALE_WHILE_REVALIDATE_SEC: u32 = 600;
pub const PRIVATE_CACHE_CONTROL: &str = "private, no-store";

/// 8 MiB is far above any page (≤500 items); larger bodies pass untouched.
const ETAG_BODY_CAP: usize = 8 * 1024 * 1024;

pub fn public_cache_control() -> String {
    format!(
        "public, s-maxage={PUBLIC_S_MAXAGE_SEC}, stale-while-revalidate={PUBLIC_STALE_WHILE_REVALIDATE_SEC}"
    )
}

pub fn weak_etag(body: &[u8]) -> String {
    // Deterministic across replicas (DefaultHasher::new() has fixed keys),
    // which is what makes If-None-Match work through a multi-replica CDN.
    let mut h = DefaultHasher::new();
    body.hash(&mut h);
    format!("W/\"{:016x}-{}\"", h.finish(), body.len())
}

pub async fn public_cache_layer(req: Request, next: Next) -> Response {
    let cacheable_route = req.uri().path().starts_with("/v1/");
    let is_get = req.method() == Method::GET;
    let anonymous = req.headers().get(header::AUTHORIZATION).is_none();
    let if_none_match = req.headers().get(header::IF_NONE_MATCH).cloned();

    let mut resp = next.run(req).await;
    if !cacheable_route || !is_get || resp.status() != StatusCode::OK {
        return resp;
    }
    if !anonymous {
        resp.headers_mut().insert(
            header::CACHE_CONTROL,
            HeaderValue::from_static(PRIVATE_CACHE_CONTROL),
        );
        return resp;
    }

    let (mut parts, body) = resp.into_parts();
    let bytes = match to_bytes(body, ETAG_BODY_CAP).await {
        Ok(b) => b,
        Err(_) => {
            return Response::from_parts(parts, Body::empty());
        }
    };
    let etag = weak_etag(&bytes);
    parts.headers.insert(
        header::CACHE_CONTROL,
        HeaderValue::from_str(&public_cache_control()).expect("static header"),
    );
    parts
        .headers
        .insert(header::ETAG, HeaderValue::from_str(&etag).expect("etag header"));
    if if_none_match.as_ref().and_then(|v| v.to_str().ok()) == Some(etag.as_str()) {
        parts.status = StatusCode::NOT_MODIFIED;
        parts.headers.remove(header::CONTENT_LENGTH);
        return Response::from_parts(parts, Body::empty());
    }
    Response::from_parts(parts, Body::from(bytes))
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::{middleware::from_fn, routing::get, Router};
    use tower::ServiceExt as _;

    fn app() -> Router {
        Router::new()
            .route("/v1/ping", get(|| async { "pong" }))
            .route("/health", get(|| async { "ok" }))
            .layer(from_fn(public_cache_layer))
    }

    #[tokio::test]
    async fn anonymous_get_is_public_with_etag_and_304() {
        let resp = app()
            .oneshot(Request::get("/v1/ping").body(Body::empty()).unwrap())
            .await
            .unwrap();
        assert_eq!(resp.status(), StatusCode::OK);
        assert_eq!(
            resp.headers()[header::CACHE_CONTROL],
            public_cache_control().as_str()
        );
        let etag = resp.headers()[header::ETAG].to_str().unwrap().to_string();
        assert!(etag.starts_with("W/\""));

        let resp = app()
            .oneshot(
                Request::get("/v1/ping")
                    .header(header::IF_NONE_MATCH, etag.clone())
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(resp.status(), StatusCode::NOT_MODIFIED);
        assert_eq!(resp.headers()[header::ETAG].to_str().unwrap(), etag);
        assert!(to_bytes(resp.into_body(), 1024).await.unwrap().is_empty());
    }

    #[tokio::test]
    async fn authenticated_get_is_private_without_etag() {
        let resp = app()
            .oneshot(
                Request::get("/v1/ping")
                    .header(header::AUTHORIZATION, "Bearer x")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(resp.status(), StatusCode::OK);
        assert_eq!(
            resp.headers()[header::CACHE_CONTROL],
            PRIVATE_CACHE_CONTROL
        );
        assert!(resp.headers().get(header::ETAG).is_none());
    }

    #[tokio::test]
    async fn non_v1_routes_untouched() {
        let resp = app()
            .oneshot(Request::get("/health").body(Body::empty()).unwrap())
            .await
            .unwrap();
        assert!(resp.headers().get(header::CACHE_CONTROL).is_none());
    }

    #[test]
    fn etag_is_deterministic_and_content_sensitive() {
        assert_eq!(weak_etag(b"abc"), weak_etag(b"abc"));
        assert_ne!(weak_etag(b"abc"), weak_etag(b"abd"));
    }
}
