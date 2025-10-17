use serde::Deserialize;
use std::env;

#[derive(Debug, Clone, Deserialize)]
pub struct Config {
    pub server: ServerConfig,
    pub database: DatabaseConfig,
    pub supabase: SupabaseConfig,
    pub encryption: EncryptionConfig,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ServerConfig {
    pub host: String,
    pub port: u16,
    pub cors_origins: Vec<String>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct DatabaseConfig {
    pub url: String,
    pub max_connections: u32,
}

#[derive(Debug, Clone, Deserialize)]
pub struct SupabaseConfig {
    pub url: String,
    pub anon_key: String,
    pub service_role_key: String,
    pub jwt_secret: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct EncryptionConfig {
    pub key: String,
}

impl Config {
    pub fn from_env() -> Result<Self, anyhow::Error> {
        dotenvy::dotenv().ok();

        // Read JWT secret and handle quotes/special characters
        let jwt_secret = env::var("SUPABASE_JWT_SECRET")
            .expect("SUPABASE_JWT_SECRET must be set")
            .trim()
            .trim_matches('"')
            .trim_matches('\'')
            .to_string();

        Ok(Config {
            server: ServerConfig {
                host: env::var("SERVER_HOST").unwrap_or_else(|_| "127.0.0.1".to_string()),
                port: env::var("SERVER_PORT")
                    .unwrap_or_else(|_| "3000".to_string())
                    .parse()?,
                cors_origins: env::var("CORS_ORIGINS")
                    .unwrap_or_else(|_| "http://localhost:3000".to_string())
                    .split(',')
                    .map(|s| s.trim().to_string())
                    .collect(),
            },
            database: DatabaseConfig {
                url: env::var("DATABASE_URL")
                    .expect("DATABASE_URL must be set"),
                max_connections: env::var("DATABASE_MAX_CONNECTIONS")
                    .unwrap_or_else(|_| "5".to_string())
                    .parse()?,
            },
            supabase: SupabaseConfig {
                url: env::var("SUPABASE_URL")
                    .expect("SUPABASE_URL must be set"),
                anon_key: env::var("SUPABASE_ANON_KEY")
                    .expect("SUPABASE_ANON_KEY must be set"),
                service_role_key: env::var("SUPABASE_SERVICE_ROLE_KEY")
                    .expect("SUPABASE_SERVICE_ROLE_KEY must be set"),
                jwt_secret,
            },
            encryption: EncryptionConfig {
                key: env::var("ENCRYPTION_KEY")
                    .expect("ENCRYPTION_KEY must be set"),
            },
        })
    }
}

