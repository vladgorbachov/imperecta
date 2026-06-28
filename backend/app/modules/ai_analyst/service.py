"""AI analyst chat core: persists session/messages and calls Anthropic."""

from __future__ import annotations

import time
from uuid import UUID, uuid4

from anthropic import AsyncAnthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.app_tables import AIChatMessage, AIChatSession
from app.models.core import User
from app.modules.ai_analyst.claude_client import resolve_claude_model
from app.modules.persist.chat_write import (
    build_chat_message_fields,
    build_chat_session_fields,
    write_chat_async,
)
from app.modules.persist.logs_write import build_api_log_fields, write_logs_async

settings = Settings()

SYSTEM_PROMPT: str = (
    "You are Imperecta AI Analyst. Answer in the user's language and use "
    "markdown."
)

# Recent-message window fed back into Anthropic per turn. Bounds latency and
# token cost; raising it should be paired with a context-window check.
CHAT_HISTORY_DEPTH: int = 20

# Max tokens for a single assistant reply (Anthropic Messages API).
CHAT_MAX_TOKENS: int = 2000

# Session title is derived from the first user message, truncated to this many
# characters so it fits in admin lists without ellipsing the column.
SESSION_TITLE_MAX_LEN: int = 100


def _get_client() -> AsyncAnthropic | None:
    """Return a configured Anthropic client, or None when the key is absent.

    Callers must handle the None case explicitly; we never substitute a fake
    response for a missing API key (Rule 3).
    """
    if not settings.claude_api_key:
        return None
    return AsyncAnthropic(api_key=settings.claude_api_key)


async def chat(
    db: AsyncSession,
    user: User,
    session_id: UUID | None,
    message: str,
    context_type: str = "general",
    context_id: UUID | None = None,
) -> dict:
    """Persist a chat turn and call Anthropic. Raises ValueError on missing
    Claude config or on a session_id that does not belong to the caller."""
    client = _get_client()
    if not client:
        raise ValueError("Claude API key not configured")

    if session_id is not None:
        existing = (
            await db.execute(
                select(AIChatSession.id).where(
                    AIChatSession.id == session_id,
                    AIChatSession.user_id == user.id,
                ),
            )
        ).scalar_one_or_none()
        if existing is None:
            raise ValueError("Session not found")
        active_session_id = session_id
    else:
        active_session_id = uuid4()
        session_result = await write_chat_async(
            table="ai_chat_sessions",
            operation="insert",
            kind="session_create",
            fields=build_chat_session_fields(
                id=active_session_id,
                user_id=user.id,
                context_type=context_type,
                context_id=context_id,
                title=message[:SESSION_TITLE_MAX_LEN],
            ),
            reject_source="ai_analyst_session_create",
        )
        if not session_result.ok:
            raise ValueError("Failed to create chat session")

    user_msg_result = await write_chat_async(
        table="ai_chat_messages",
        operation="insert",
        kind="message_append",
        fields=build_chat_message_fields(
            session_id=active_session_id,
            role="user",
            content=message,
        ),
        reject_source="ai_analyst_message_user",
    )
    if not user_msg_result.ok:
        raise ValueError("Failed to persist user message")

    history = list(
        reversed(
            (
                await db.execute(
                    select(AIChatMessage)
                    .where(AIChatMessage.session_id == active_session_id)
                    .order_by(AIChatMessage.created_at.desc())
                    .limit(CHAT_HISTORY_DEPTH)
                )
            ).scalars().all()
        )
    )
    messages = [{"role": m.role, "content": m.content} for m in history]

    model_id = await resolve_claude_model(settings.claude_model, settings.claude_api_key)
    start = time.time()
    response = await client.messages.create(
        model=model_id,
        max_tokens=CHAT_MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    duration_ms = int((time.time() - start) * 1000)

    assistant_content = response.content[0].text if response.content else ""
    tokens_used = 0
    if response.usage is not None:
        tokens_used = (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0)

    await write_logs_async(
        table="api_logs",
        rows=[
            build_api_log_fields(
                service="claude",
                endpoint="/v1/messages",
                method="POST",
                status="success",
                status_code=200,
                duration_ms=duration_ms,
                tokens_used=tokens_used,
            ),
        ],
        reject_source="ai_analyst",
    )
    assistant_result = await write_chat_async(
        table="ai_chat_messages",
        operation="insert",
        kind="message_append",
        fields=build_chat_message_fields(
            session_id=active_session_id,
            role="assistant",
            content=assistant_content,
            tokens_used=tokens_used,
            model_used=model_id,
            duration_ms=duration_ms,
        ),
        reject_source="ai_analyst_message_assistant",
    )
    if not assistant_result.ok:
        raise ValueError("Failed to persist assistant message")

    return {
        "session_id": active_session_id,
        "response": assistant_content,
        "tokens_used": tokens_used,
        "duration_ms": duration_ms,
    }
