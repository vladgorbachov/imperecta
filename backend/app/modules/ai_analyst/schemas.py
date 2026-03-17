"""AI chat request/response schemas."""

from uuid import UUID

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    session_id: int | None = None
    context_type: str = Field(default="general", max_length=50)
    context_id: UUID | None = None


class ChatResponse(BaseModel):
    session_id: int
    response: str
    tokens_used: int
    duration_ms: int


class SessionListItem(BaseModel):
    id: int
    title: str | None
    context_type: str | None
    created_at: str
    updated_at: str
    message_count: int


class MessageItem(BaseModel):
    role: str
    content: str
    created_at: str


class SessionDetailResponse(BaseModel):
    id: int
    title: str | None
    context_type: str | None
    messages: list[MessageItem]
