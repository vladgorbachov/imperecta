use axum::{
    middleware,
    routing::{get, post, put, delete},
    Router,
};
use sqlx::PgPool;
use std::sync::Arc;
use tower_http::cors::{CorsLayer, Any};

use crate::auth::{AuthMiddleware, SupabaseClient};
use super::{users, organizations};

pub fn create_router(pool: PgPool, supabase: Arc<SupabaseClient>) -> Router {
    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    // Public routes
    let public_routes = Router::new()
        .route("/health", get(health_check));

    // User routes (protected)
    let user_routes = Router::new()
        .route("/users/:id", get(users::get_user))
        .route("/users/supabase/:supabase_user_id", get(users::get_user_by_supabase_id))
        .route("/users", post(users::create_user))
        .route("/users/:id", put(users::update_user))
        .route("/users/:id", delete(users::delete_user))
        .route_layer(middleware::from_fn_with_state(
            supabase.clone(),
            AuthMiddleware::require_auth,
        ));

    // Organization routes (protected)
    let organization_routes = Router::new()
        .route("/organizations", post(organizations::create_organization))
        .route("/organizations/:id", get(organizations::get_organization))
        .route("/organizations/:id/members", get(organizations::get_organization_with_members))
        .route("/organizations/:id", put(organizations::update_organization))
        .route("/organizations/:id", delete(organizations::delete_organization))
        .route("/users/:user_id/organizations", get(organizations::get_user_organizations))
        .route_layer(middleware::from_fn_with_state(
            supabase.clone(),
            AuthMiddleware::require_auth,
        ));

    Router::new()
        .nest("/api", public_routes)
        .nest("/api", user_routes)
        .nest("/api", organization_routes)
        .layer(cors)
        .with_state(pool)
        .with_state(supabase)
}

async fn health_check() -> &'static str {
    "OK"
}

