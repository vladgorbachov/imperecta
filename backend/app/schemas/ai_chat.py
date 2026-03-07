"""AI chat request/response schemas."""

from uuid import UUID

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request body for POST /api/ai/chat."""

    message: str = Field(..., min_length=1, max_length=5000)
    session_id: int | None = None
    context_type: str = Field(default="general", max_length=50)
    context_id: UUID | None = None


class ChatResponse(BaseModel):
    """Response for POST /api/ai/chat."""

    session_id: int
    response: str
    tokens_used: int
    duration_ms: int


class SessionListItem(BaseModel):
    """Session list item for GET /api/ai/sessions."""

    id: int
    title: str | None
    context_type: str | None
    created_at: str
    updated_at: str
    message_count: int


class MessageItem(BaseModel):
    """Single message in session detail."""

    role: str
    content: str
    created_at: str


class SessionDetailResponse(BaseModel):
    """Session detail with messages for GET /api/ai/sessions/{id}."""

    id: int
    title: str | None
    context_type: str | None
    messages: list[MessageItem]
