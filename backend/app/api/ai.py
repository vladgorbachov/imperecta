"""AI chat API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.models import AIChatMessage, AIChatSession
from app.schemas.ai_chat import (
    ChatRequest,
    ChatResponse,
    MessageItem,
    SessionDetailResponse,
    SessionListItem,
)
from app.services.ai_chat_service import chat as ai_chat

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/chat", response_model=ChatResponse)
async def post_chat(
    body: ChatRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ChatResponse:
    """
    Send message to AI analyst. Creates new session or continues existing one.
    """
    import logging

    logger = logging.getLogger(__name__)
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
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.warning("AI chat failed: %s", e)
        raise HTTPException(
            status_code=503,
            detail="AI chat service temporarily unavailable",
        )


@router.get("/sessions", response_model=list[SessionListItem])
async def list_sessions(
    current_user: CurrentUser,
    db: DbSession,
) -> list[SessionListItem]:
    """List user's chat sessions (last 20), ordered by updated_at DESC."""
    result = await db.execute(
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
    rows = result.all()
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
async def get_session(
    session_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> SessionDetailResponse:
    """Get session with all messages. Requires ownership."""
    session_result = await db.execute(
        select(AIChatSession)
        .where(
            AIChatSession.id == session_id,
            AIChatSession.user_id == current_user.id,
        )
        .options(selectinload(AIChatSession.messages))
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    messages = [
        MessageItem(
            role=m.role,
            content=m.content,
            created_at=m.created_at.isoformat(),
        )
        for m in session.messages
    ]

    return SessionDetailResponse(
        id=session.id,
        title=session.title,
        context_type=session.context_type,
        messages=messages,
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> None:
    """Delete chat session. Requires ownership."""
    session_result = await db.execute(
        select(AIChatSession).where(
            AIChatSession.id == session_id,
            AIChatSession.user_id == current_user.id,
        )
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    await db.delete(session)
