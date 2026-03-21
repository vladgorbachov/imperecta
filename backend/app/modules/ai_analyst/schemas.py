"""AI chat request/response schemas (v2 ai_chat_sessions / ai_chat_messages)."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    session_id: UUID | None = None
    context_type: str = Field(default="general", max_length=50)
    context_id: UUID | None = None


class ChatResponse(BaseModel):
    session_id: UUID
    response: str
    tokens_used: int
    duration_ms: int


class SessionListItem(BaseModel):
    id: UUID
    title: str | None
    context_type: str | None
    created_at: str
    updated_at: str
    message_count: int
    total_tokens: int = 0


class MessageItem(BaseModel):
    role: str
    content: str
    created_at: str
    tool_calls: dict[str, Any] | None = None
    tokens_used: int | None = None


class SessionDetailResponse(BaseModel):
    id: UUID
    title: str | None
    context_type: str | None
    message_count: int | None = None
    total_tokens: int | None = None
    messages: list[MessageItem]
