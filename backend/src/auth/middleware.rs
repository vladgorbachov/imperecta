use axum::{
    extract::{Request, State},
    http::{StatusCode, header::AUTHORIZATION},
    middleware::Next,
    response::Response,
};
use std::sync::Arc;
use super::supabase::{SupabaseClient, Claims};

pub struct AuthMiddleware;

impl AuthMiddleware {
    pub async fn require_auth(
        State(supabase): State<Arc<SupabaseClient>>,
        mut request: Request,
        next: Next,
    ) -> Result<Response, StatusCode> {
        let auth_header = request
            .headers()
            .get(AUTHORIZATION)
            .and_then(|value| value.to_str().ok())
            .ok_or(StatusCode::UNAUTHORIZED)?;

        let token = auth_header
            .strip_prefix("Bearer ")
            .ok_or(StatusCode::UNAUTHORIZED)?;

        let claims = supabase
            .verify_token(token)
            .await
            .map_err(|e| {
                tracing::error!("Token verification failed: {}", e);
                StatusCode::UNAUTHORIZED
            })?;

        request.extensions_mut().insert(claims);
        Ok(next.run(request).await)
    }
}

// Extension trait to get claims from request
pub trait ClaimsExt {
    fn claims(&self) -> Option<&Claims>;
}

impl ClaimsExt for Request {
    fn claims(&self) -> Option<&Claims> {
        self.extensions().get::<Claims>()
    }
}

