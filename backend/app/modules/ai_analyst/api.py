"""AI chat API. AI1 reduced this to the single live route (POST /ai/chat);
the session-list/detail/delete routes had zero frontend consumers and were
removed (the live chat UI keeps message history in local React state pending
the future AI agent rewrite)."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.common.deps import CurrentUser, DbSession
from app.entitlements import Feature, has_feature
from app.models.core import User
from app.modules.ai_analyst.schemas import ChatRequest, ChatResponse
from app.modules.ai_analyst.service import chat as ai_chat


def require_ai_analyst_feature(current_user: CurrentUser) -> User:
    """Router-level Feature.AI_ANALYST gate.

    Single source of truth for the entitlement check; replaces the four
    inline duplicates that pre-AI1 lived on every handler.
    """
    if not has_feature(current_user.plan, Feature.AI_ANALYST):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI Analyst is available on Paid Full plan. Upgrade to unlock.",
        )
    return current_user


router = APIRouter(
    prefix="/ai",
    tags=["ai"],
    dependencies=[Depends(require_ai_analyst_feature)],
)


@router.post("/chat", response_model=ChatResponse)
async def post_chat(
    body: ChatRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ChatResponse:
    try:
        result = await ai_chat(
            db=db,
            user=current_user,
            session_id=body.session_id,
            message=body.message,
            context_type=body.context_type,
            context_id=body.context_id,
        )
    except ValueError as error:
        message = str(error)
        if message == "Session not found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=message,
            ) from error
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=message,
        ) from error
    return ChatResponse(**result)
