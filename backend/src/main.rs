mod api;
mod auth;
mod config;
mod db;

use std::sync::Arc;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

use crate::{
    api::routes::create_router,
    auth::SupabaseClient,
    config::Config,
    db::create_pool,
};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Initialize tracing
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "imperecta=debug,tower_http=debug,axum=trace".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    // Load configuration
    let config = Config::from_env()?;
    tracing::info!("Configuration loaded");

    // Create database pool
    let pool = create_pool(&config.database.url, config.database.max_connections).await?;
    tracing::info!("Database pool created");

    // Create Supabase client
    let supabase = Arc::new(SupabaseClient::new(
        config.supabase.url.clone(),
        config.supabase.jwt_secret.clone(),
    ));
    tracing::info!("Supabase client initialized");

    // Create router
    let app = create_router(pool, supabase);

    // Start server
    let addr = format!("{}:{}", config.server.host, config.server.port);
    let listener = tokio::net::TcpListener::bind(&addr).await?;
    tracing::info!("Server listening on {}", addr);

    axum::serve(listener, app).await?;

    Ok(())
}

