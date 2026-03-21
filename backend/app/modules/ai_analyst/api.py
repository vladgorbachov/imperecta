"""AI chat API endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.common.deps import CurrentUser, DbSession
from app.entitlements import Feature, has_feature
from app.models.app_tables import AIChatMessage, AIChatSession
from app.modules.ai_analyst.schemas import (
    ChatRequest,
    ChatResponse,
    MessageItem,
    SessionDetailResponse,
    SessionListItem,
)
from app.modules.ai_analyst.service import chat as ai_chat

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/chat", response_model=ChatResponse)
async def post_chat(body: ChatRequest, current_user: CurrentUser, db: DbSession) -> ChatResponse:
    if not has_feature(current_user.plan, Feature.AI_ANALYST):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="AI Analyst is available on Paid Full plan. Upgrade to unlock.")
    try:
        result = await ai_chat(
            db=db,
            user=current_user,
            session_id=body.session_id,
            message=body.message,
            context_type=body.context_type,
            context_id=body.context_id,
        )
        return ChatResponse(**result)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


@router.get("/sessions", response_model=list[SessionListItem])
async def list_sessions(current_user: CurrentUser, db: DbSession) -> list[SessionListItem]:
    if not has_feature(current_user.plan, Feature.AI_ANALYST):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="AI Analyst is available on Paid Full plan. Upgrade to unlock.")
    rows = (
        await db.execute(
            select(
                AIChatSession.id,
                AIChatSession.title,
                AIChatSession.context_type,
                AIChatSession.created_at,
                AIChatSession.updated_at,
                func.count(AIChatMessage.id).label("message_count"),
            )
            .outerjoin(AIChatMessage, AIChatMessage.session_id == AIChatSession.id)
            .where(AIChatSession.user_id == current_user.id)
            .group_by(AIChatSession.id)
            .order_by(AIChatSession.updated_at.desc())
            .limit(20)
        )
    ).all()
    return [
        SessionListItem(
            id=r.id,
            title=r.title,
            context_type=r.context_type,
            created_at=r.created_at.isoformat(),
            updated_at=r.updated_at.isoformat(),
            message_count=r.message_count,
        )
        for r in rows
    ]


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(session_id: UUID, current_user: CurrentUser, db: DbSession) -> SessionDetailResponse:
    if not has_feature(current_user.plan, Feature.AI_ANALYST):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="AI Analyst is available on Paid Full plan. Upgrade to unlock.")
    session = (
        await db.execute(
            select(AIChatSession)
            .where(AIChatSession.id == session_id, AIChatSession.user_id == current_user.id)
            .options(selectinload(AIChatSession.messages))
        )
    ).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return SessionDetailResponse(
        id=session.id,
        title=session.title,
        context_type=session.context_type,
        messages=[MessageItem(role=m.role, content=m.content or "", created_at=m.created_at.isoformat()) for m in session.messages],
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: UUID, current_user: CurrentUser, db: DbSession) -> None:
    if not has_feature(current_user.plan, Feature.AI_ANALYST):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="AI Analyst is available on Paid Full plan. Upgrade to unlock.")
    session = (
        await db.execute(select(AIChatSession).where(AIChatSession.id == session_id, AIChatSession.user_id == current_user.id))
    ).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    await db.delete(session)
