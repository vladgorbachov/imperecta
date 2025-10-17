use axum::{
    extract::{Path, State},
    Json,
};
use sqlx::PgPool;
use uuid::Uuid;

use crate::db::schema::{
    CreateOrganizationRequest, UpdateOrganizationRequest, Organization,
    OrganizationWithMembers, MemberWithUser, User, Role
};
use super::{ApiResult, ApiError};

pub async fn get_organization(
    State(pool): State<PgPool>,
    Path(id): Path<Uuid>,
) -> ApiResult<Json<Organization>> {
    let org = sqlx::query_as::<_, Organization>(
        "SELECT * FROM organizations WHERE id = $1"
    )
    .bind(id)
    .fetch_one(&pool)
    .await?;

    Ok(Json(org))
}

pub async fn get_organization_with_members(
    State(pool): State<PgPool>,
    Path(id): Path<Uuid>,
) -> ApiResult<Json<OrganizationWithMembers>> {
    let org = sqlx::query_as::<_, Organization>(
        "SELECT * FROM organizations WHERE id = $1"
    )
    .bind(id)
    .fetch_one(&pool)
    .await?;

    // Get organization members with their user and role data
    let member_ids: Vec<(Uuid, Uuid, Option<chrono::DateTime<chrono::Utc>>, bool)> = sqlx::query_as(
        "SELECT om.user_id, om.role_id, om.joined_at, om.is_active
         FROM organization_members om
         WHERE om.organization_id = $1
         ORDER BY om.created_at ASC"
    )
    .bind(id)
    .fetch_all(&pool)
    .await?;

    let mut members = Vec::new();
    
    for (user_id, role_id, joined_at, is_active) in member_ids {
        let user = sqlx::query_as::<_, User>(
            "SELECT * FROM users WHERE id = $1"
        )
        .bind(user_id)
        .fetch_one(&pool)
        .await?;

        let role = sqlx::query_as::<_, Role>(
            "SELECT * FROM roles WHERE id = $1"
        )
        .bind(role_id)
        .fetch_one(&pool)
        .await?;

        members.push(MemberWithUser {
            user,
            role,
            joined_at,
            is_active,
        });
    }

    Ok(Json(OrganizationWithMembers {
        organization: org,
        members,
    }))
}

pub async fn create_organization(
    State(pool): State<PgPool>,
    Json(req): Json<CreateOrganizationRequest>,
) -> ApiResult<Json<Organization>> {
    // Validate slug format
    if !req.slug.chars().all(|c| c.is_ascii_alphanumeric() || c == '-') {
        return Err(ApiError::BadRequest(
            "Slug must contain only lowercase letters, numbers, and hyphens".to_string()
        ));
    }

    let org = sqlx::query_as::<_, Organization>(
        "INSERT INTO organizations (name, slug, description, owner_id, max_members) 
         VALUES ($1, $2, $3, $4, $5) 
         RETURNING *"
    )
    .bind(&req.name)
    .bind(&req.slug)
    .bind(&req.description)
    .bind(Uuid::new_v4()) // TODO: Get from auth context
    .bind(req.max_members.unwrap_or(10))
    .fetch_one(&pool)
    .await
    .map_err(|e| {
        if e.to_string().contains("organizations_slug_unique") {
            ApiError::BadRequest("Organization slug already exists".to_string())
        } else {
            ApiError::from(e)
        }
    })?;

    Ok(Json(org))
}

pub async fn update_organization(
    State(pool): State<PgPool>,
    Path(id): Path<Uuid>,
    Json(req): Json<UpdateOrganizationRequest>,
) -> ApiResult<Json<Organization>> {
    let org = sqlx::query_as::<_, Organization>(
        "UPDATE organizations 
         SET name = COALESCE($2, name),
             description = COALESCE($3, description),
             max_members = COALESCE($4, max_members),
             is_active = COALESCE($5, is_active),
             updated_at = NOW()
         WHERE id = $1
         RETURNING *"
    )
    .bind(id)
    .bind(req.name)
    .bind(req.description)
    .bind(req.max_members)
    .bind(req.is_active)
    .fetch_one(&pool)
    .await?;

    Ok(Json(org))
}

pub async fn delete_organization(
    State(pool): State<PgPool>,
    Path(id): Path<Uuid>,
) -> ApiResult<Json<serde_json::Value>> {
    sqlx::query("DELETE FROM organizations WHERE id = $1")
        .bind(id)
        .execute(&pool)
        .await?;

    Ok(Json(serde_json::json!({ "success": true })))
}

pub async fn get_user_organizations(
    State(pool): State<PgPool>,
    Path(user_id): Path<Uuid>,
) -> ApiResult<Json<Vec<Organization>>> {
    let orgs = sqlx::query_as::<_, Organization>(
        "SELECT o.* FROM organizations o
         JOIN organization_members om ON om.organization_id = o.id
         WHERE om.user_id = $1 AND om.is_active = true
         ORDER BY o.created_at DESC"
    )
    .bind(user_id)
    .fetch_all(&pool)
    .await?;

    Ok(Json(orgs))
}

