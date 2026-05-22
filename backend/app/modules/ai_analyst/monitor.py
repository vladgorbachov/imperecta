"""Claude API health check and monitoring."""

import time

import httpx

from app.config import Settings
from app.modules.ai_analyst.claude_client import resolve_claude_model

settings = Settings()


async def check_claude_api_health() -> dict:
    if not settings.claude_api_key:
        return {"status": "not_configured", "message": "CLAUDE_API_KEY not set", "latency_ms": 0}
    start = time.time()
    try:
        model_id = await resolve_claude_model(settings.claude_model, settings.claude_api_key)
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.claude_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={"model": model_id, "max_tokens": 1, "messages": [{"role": "user", "content": "ping"}]},
            )
        return {
            "status": "online" if response.status_code == 200 else "error",
            "status_code": response.status_code,
            "latency_ms": int((time.time() - start) * 1000),
        }
    except Exception as error:
        return {"status": "error", "message": str(error), "latency_ms": int((time.time() - start) * 1000)}
