"""Digests API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models import Digest
from app.schemas.digest import DigestResponse

router = APIRouter()


@router.get("/", response_model=list[DigestResponse])
async def list_digests(
    current_user: CurrentUser,
    db: DbSession,
) -> list[DigestResponse]:
    """List digests of current user."""
    result = await db.execute(
        select(Digest)
        .where(Digest.user_id == current_user.id)
        .order_by(Digest.created_at.desc())
    )
    digests = result.scalars().all()
    return [DigestResponse.model_validate(d) for d in digests]


@router.get("/{id}", response_model=DigestResponse)
async def get_digest(
    id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> DigestResponse:
    """Get digest by id."""
    result = await db.execute(
        select(Digest).where(
            Digest.id == id,
            Digest.user_id == current_user.id,
        )
    )
    digest = result.scalar_one_or_none()
    if digest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Digest not found")
    return DigestResponse.model_validate(digest)
