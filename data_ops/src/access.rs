//! Access control on the read path (legal clean-up WP2, counsel §3.8):
//! every `/v1/*` request carries a valid HS256 JWT (the FastAPI backend's
//! secret) and spends from the caller's hourly budget.
//!
//! The budget is a GCRA (generic cell rate algorithm) per user — O(1) time,
//! one f64 per user, no windows or queues: a request is admitted when the
//! theoretical arrival time (TAT) is not more than one window ahead of
//! now, and moves the TAT by one emission interval. Per replica (data-ops
//! runs one), pruned lazily; WP10 replaces it with the metered read door.

use std::{
    collections::HashMap,
    sync::Mutex,
    time::{Duration, Instant},
};

use axum::{
    extract::{Request, State},
    http::{header, HeaderValue, StatusCode},
    middleware::Next,
    response::{IntoResponse, Response},
    Json,
};
use jsonwebtoken::{decode, Algorithm, DecodingKey, Validation};
use serde_json::json;

use crate::{AppState, Claims};

pub const WINDOW: Duration = Duration::from_secs(3600);
/// Entries older than this since their last admission are dropped on the
/// next prune (a full window: the TAT can never be further ahead).
const PRUNE_EVERY: u64 = 4096;

pub struct RateLimiter {
    limit_per_window: u32,
    emission: Duration,
    state: Mutex<(HashMap<String, Instant>, u64)>,
    epoch: Instant,
}

impl RateLimiter {
    pub fn new(limit_per_window: u32) -> Self {
        let emission = if limit_per_window == 0 {
            Duration::ZERO
        } else {
            WINDOW / limit_per_window
        };
        Self {
            limit_per_window,
            emission,
            state: Mutex::new((HashMap::new(), 0)),
            epoch: Instant::now(),
        }
    }

    /// Admit or refuse one request for `key` at `now`; returns the seconds
    /// to wait when refused.
    pub fn check(&self, key: &str, now: Instant) -> Result<(), u64> {
        if self.limit_per_window == 0 {
            return Ok(());
        }
        let mut guard = self.state.lock().expect("rate limiter poisoned");
        let (map, calls) = &mut *guard;
        *calls += 1;
        if *calls % PRUNE_EVERY == 0 {
            map.retain(|_, tat| *tat + WINDOW > now);
        }
        // TAT below `now` means the bucket drained: restart from now.
        let tat = map.get(key).copied().unwrap_or(self.epoch).max(now);
        // Burst allowance = the whole window: TAT may run ahead of now by
        // (limit - 1) emissions before the next request is refused.
        let allow_until = now + WINDOW - self.emission;
        if tat > allow_until {
            let wait = tat - allow_until;
            return Err(wait.as_secs().max(1));
        }
        map.insert(key.to_string(), tat + self.emission);
        Ok(())
    }
}

fn unauthorized(detail: &str) -> Response {
    (StatusCode::UNAUTHORIZED, Json(json!({ "detail": detail }))).into_response()
}

pub fn decode_bearer(secret: &str, auth: Option<&HeaderValue>) -> Result<Claims, &'static str> {
    let raw = auth
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .ok_or("missing bearer token")?;
    let mut validation = Validation::new(Algorithm::HS256);
    validation.validate_exp = true;
    decode::<Claims>(raw, &DecodingKey::from_secret(secret.as_bytes()), &validation)
        .map(|d| d.claims)
        .map_err(|_| "invalid token")
}

/// `/v1/*`: JWT required, then the caller's hourly budget. `/health` and
/// everything else pass untouched.
pub async fn access_layer(State(state): State<AppState>, req: Request, next: Next) -> Response {
    if !req.uri().path().starts_with("/v1/") {
        return next.run(req).await;
    }
    let claims = match decode_bearer(&state.jwt_secret, req.headers().get(header::AUTHORIZATION)) {
        Ok(c) => c,
        Err(detail) => return unauthorized(detail),
    };
    if let Err(wait) = state.limiter.check(&claims.sub, Instant::now()) {
        let mut resp = (
            StatusCode::TOO_MANY_REQUESTS,
            Json(json!({ "detail": "rate_limited" })),
        )
            .into_response();
        resp.headers_mut().insert(
            header::RETRY_AFTER,
            HeaderValue::from_str(&wait.to_string()).expect("digits"),
        );
        return resp;
    }
    let mut req = req;
    req.extensions_mut().insert(claims);
    next.run(req).await
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn gcra_admits_limit_then_refuses_then_recovers() {
        let rl = RateLimiter::new(3);
        let t0 = Instant::now();
        assert!(rl.check("u", t0).is_ok());
        assert!(rl.check("u", t0).is_ok());
        assert!(rl.check("u", t0).is_ok());
        let wait = rl.check("u", t0).unwrap_err();
        assert!(wait >= 1 && wait <= WINDOW.as_secs() / 3 + 1);
        // one emission interval later one more request fits
        assert!(rl.check("u", t0 + WINDOW / 3).is_ok());
        assert!(rl.check("u", t0 + WINDOW / 3).is_err());
        // other users have their own budget
        assert!(rl.check("v", t0).is_ok());
        // a full window later the budget is back
        assert!(rl.check("u", t0 + WINDOW * 2).is_ok());
    }

    #[test]
    fn zero_limit_disables_the_guard() {
        let rl = RateLimiter::new(0);
        for _ in 0..10 {
            assert!(rl.check("u", Instant::now()).is_ok());
        }
    }

    #[test]
    fn bearer_parsing() {
        assert_eq!(decode_bearer("s", None).unwrap_err(), "missing bearer token");
        let bad = HeaderValue::from_static("Bearer nope");
        assert_eq!(decode_bearer("s", Some(&bad)).unwrap_err(), "invalid token");
    }
}
