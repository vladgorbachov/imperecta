"""AI chat request/response schemas (v2 ai_chat_sessions / ai_chat_messages).

AI1 dropped the SessionListItem / SessionDetailResponse / MessageItem schemas
that fed the deleted /ai/sessions* routes; they declared always-null/zero
fields the handler never filled (Rule 3).
"""

from uuid import UUID

from pydantic import BaseModel, Field

CHAT_MESSAGE_MAX_LEN: int = 5000
CHAT_CONTEXT_TYPE_MAX_LEN: int = 50


class ChatRequest(BaseModel):
    """Body of POST /ai/chat. context_id/context_type are reserved for the
    future AI agent; chat() does not consume them yet but stores them on the
    session so they survive into the agent rewrite."""

    message: str = Field(..., min_length=1, max_length=CHAT_MESSAGE_MAX_LEN)
    session_id: UUID | None = None
    context_type: str = Field(default="general", max_length=CHAT_CONTEXT_TYPE_MAX_LEN)
    context_id: UUID | None = None


class ChatResponse(BaseModel):
    """Response of POST /ai/chat. tokens_used / duration_ms are real values
    measured during the Anthropic call (not placeholders)."""

    session_id: UUID
    response: str
    tokens_used: int
    duration_ms: int
