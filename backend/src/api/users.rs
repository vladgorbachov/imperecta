use axum::{
    extract::{Path, State},
    Json,
};
use sqlx::PgPool;
use uuid::Uuid;

use crate::db::schema::{CreateUserRequest, UpdateUserRequest, User};
use super::ApiResult;

pub async fn get_user(
    State(pool): State<PgPool>,
    Path(id): Path<Uuid>,
) -> ApiResult<Json<User>> {
    let user = sqlx::query_as::<_, User>(
        "SELECT * FROM users WHERE id = $1"
    )
    .bind(id)
    .fetch_one(&pool)
    .await?;

    Ok(Json(user))
}

pub async fn get_user_by_supabase_id(
    State(pool): State<PgPool>,
    Path(supabase_user_id): Path<Uuid>,
) -> ApiResult<Json<User>> {
    let user = sqlx::query_as::<_, User>(
        "SELECT * FROM users WHERE supabase_user_id = $1"
    )
    .bind(supabase_user_id)
    .fetch_one(&pool)
    .await?;

    Ok(Json(user))
}

pub async fn create_user(
    State(pool): State<PgPool>,
    Json(req): Json<CreateUserRequest>,
) -> ApiResult<Json<User>> {
    let user = sqlx::query_as::<_, User>(
        "INSERT INTO users (supabase_user_id, first_name, last_name, email) 
         VALUES ($1, $2, $3, $4) 
         RETURNING *"
    )
    .bind(req.supabase_user_id)
    .bind(req.first_name)
    .bind(req.last_name)
    .bind(req.email)
    .fetch_one(&pool)
    .await?;

    Ok(Json(user))
}

pub async fn update_user(
    State(pool): State<PgPool>,
    Path(id): Path<Uuid>,
    Json(req): Json<UpdateUserRequest>,
) -> ApiResult<Json<User>> {
    let user = sqlx::query_as::<_, User>(
        "UPDATE users 
         SET first_name = COALESCE($2, first_name),
             last_name = COALESCE($3, last_name),
             avatar_url = COALESCE($4, avatar_url),
             updated_at = NOW()
         WHERE id = $1
         RETURNING *"
    )
    .bind(id)
    .bind(req.first_name)
    .bind(req.last_name)
    .bind(req.avatar_url)
    .fetch_one(&pool)
    .await?;

    Ok(Json(user))
}

pub async fn delete_user(
    State(pool): State<PgPool>,
    Path(id): Path<Uuid>,
) -> ApiResult<Json<serde_json::Value>> {
    sqlx::query("DELETE FROM users WHERE id = $1")
        .bind(id)
        .execute(&pool)
        .await?;

    Ok(Json(serde_json::json!({ "success": true })))
}
