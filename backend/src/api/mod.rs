pub mod routes;
pub mod users;
pub mod organizations;

use axum::{
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};
use serde_json::json;

pub type ApiResult<T> = Result<T, ApiError>;

#[derive(Debug)]
pub enum ApiError {
    InternalError(anyhow::Error),
    NotFound(String),
    BadRequest(String),
    Unauthorized(String),
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let (status, message) = match self {
            ApiError::InternalError(e) => {
                tracing::error!("Internal error: {:?}", e);
                (StatusCode::INTERNAL_SERVER_ERROR, "Internal server error".to_string())
            }
            ApiError::NotFound(msg) => (StatusCode::NOT_FOUND, msg),
            ApiError::BadRequest(msg) => (StatusCode::BAD_REQUEST, msg),
            ApiError::Unauthorized(msg) => (StatusCode::UNAUTHORIZED, msg),
        };

        let body = Json(json!({
            "error": message,
        }));

        (status, body).into_response()
    }
}

impl From<anyhow::Error> for ApiError {
    fn from(err: anyhow::Error) -> Self {
        ApiError::InternalError(err)
    }
}

impl From<sqlx::Error> for ApiError {
    fn from(err: sqlx::Error) -> Self {
        match err {
            sqlx::Error::RowNotFound => ApiError::NotFound("Resource not found".to_string()),
            _ => ApiError::InternalError(anyhow::anyhow!(err)),
        }
    }
}

