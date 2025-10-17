use jsonwebtoken::{decode, decode_header, DecodingKey, Validation, Algorithm};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use moka::future::Cache;
use reqwest::Client;
use anyhow::{Context, Result};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Claims {
    pub sub: String,
    pub email: Option<String>,
    pub role: String,
    pub exp: usize,
    pub iat: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JWK {
    pub kty: String,
    pub n: String,
    pub e: String,
    pub alg: String,
    pub kid: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JWKS {
    pub keys: Vec<JWK>,
}

#[derive(Clone)]
pub struct SupabaseClient {
    jwt_secret: String,
    jwks_cache: Arc<Cache<String, JWKS>>,
    http_client: Client,
    supabase_url: String,
}

impl SupabaseClient {
    pub fn new(supabase_url: String, jwt_secret: String) -> Self {
        let jwks_cache = Arc::new(
            Cache::builder()
                .max_capacity(10)
                .time_to_live(std::time::Duration::from_secs(3600))
                .build(),
        );

        Self {
            jwt_secret,
            jwks_cache,
            http_client: Client::new(),
            supabase_url,
        }
    }

    pub async fn verify_token(&self, token: &str) -> Result<Claims> {
        let _header = decode_header(token)
            .context("Failed to decode JWT header")?;

        // Try to verify with JWT secret first
        let mut validation = Validation::new(Algorithm::HS256);
        validation.validate_exp = true;
        
        let decoding_key = DecodingKey::from_secret(self.jwt_secret.as_bytes());
        
        match decode::<Claims>(token, &decoding_key, &validation) {
            Ok(token_data) => Ok(token_data.claims),
            Err(e) => {
                tracing::warn!("Failed to verify token with secret: {}", e);
                // Fallback to JWK verification if needed
                Err(anyhow::anyhow!("Invalid token: {}", e))
            }
        }
    }

    async fn get_jwks(&self) -> Result<JWKS> {
        let cache_key = "jwks".to_string();
        
        if let Some(cached) = self.jwks_cache.get(&cache_key).await {
            return Ok(cached);
        }

        let url = format!("{}/.well-known/jwks.json", self.supabase_url);
        let jwks: JWKS = self.http_client
            .get(&url)
            .send()
            .await
            .context("Failed to fetch JWKS")?
            .json()
            .await
            .context("Failed to parse JWKS")?;

        self.jwks_cache.insert(cache_key, jwks.clone()).await;
        Ok(jwks)
    }
}

