"""Digests API endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.common.deps import CurrentUser, DbSession
from app.models.app_tables import Digest
from app.modules.digests.schemas import DigestResponse

router = APIRouter(prefix="/digests", tags=["digests"])


@router.get("", response_model=list[DigestResponse])
async def list_digests(current_user: CurrentUser, db: DbSession) -> list[DigestResponse]:
    digests = (
        await db.execute(select(Digest).where(Digest.user_id == current_user.id).order_by(Digest.created_at.desc()))
    ).scalars().all()
    return [DigestResponse.model_validate(digest) for digest in digests]


@router.get("/{id}", response_model=DigestResponse)
async def get_digest(id: UUID, current_user: CurrentUser, db: DbSession) -> DigestResponse:
    digest = (
        await db.execute(select(Digest).where(Digest.id == id, Digest.user_id == current_user.id))
    ).scalar_one_or_none()
    if digest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Digest not found")
    return DigestResponse.model_validate(digest)
