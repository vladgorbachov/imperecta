use sqlx::{postgres::PgPoolOptions, PgPool};
use anyhow::Result;

pub mod schema;

pub async fn create_pool(database_url: &str, max_connections: u32) -> Result<PgPool> {
    let pool = PgPoolOptions::new()
        .max_connections(max_connections)
        .connect(database_url)
        .await?;

    Ok(pool)
}

