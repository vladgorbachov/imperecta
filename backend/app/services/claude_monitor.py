"""Claude API health check and monitoring."""

import logging
import time

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)
settings = Settings()


async def check_claude_api_health() -> dict:
    """
    Perform a lightweight health check against Claude API.
    Sends a minimal request to verify connectivity and auth.
    Returns status dict with latency, status, error info.
    """
    if not settings.claude_api_key:
        return {
            "status": "not_configured",
            "message": "CLAUDE_API_KEY not set",
            "latency_ms": 0,
        }

    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.claude_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": settings.claude_model,
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "ping"}],
                },
            )
        latency = int((time.time() - start) * 1000)

        if response.status_code == 200:
            return {
                "status": "online",
                "message": "Claude API is operational",
                "latency_ms": latency,
                "status_code": 200,
            }
        if response.status_code == 401:
            return {
                "status": "auth_error",
                "message": "Invalid API key",
                "latency_ms": latency,
                "status_code": 401,
            }
        if response.status_code == 429:
            return {
                "status": "rate_limited",
                "message": "Rate limit exceeded",
                "latency_ms": latency,
                "status_code": 429,
            }
        if response.status_code == 529:
            return {
                "status": "overloaded",
                "message": "Claude API is overloaded",
                "latency_ms": latency,
                "status_code": 529,
            }
        return {
            "status": "error",
            "message": f"Unexpected status: {response.status_code}",
            "latency_ms": latency,
            "status_code": response.status_code,
        }
    except httpx.TimeoutException:
        latency = int((time.time() - start) * 1000)
        return {
            "status": "timeout",
            "message": "Request timed out (15s)",
            "latency_ms": latency,
        }
    except Exception as e:
        latency = int((time.time() - start) * 1000)
        return {
            "status": "error",
            "message": str(e),
            "latency_ms": latency,
        }


async def get_claude_api_stats(db) -> dict:
    """Get Claude API usage stats from api_logs table."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import and_, func, select

    from app.models.api_log import ApiLog

    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)

    result = await db.execute(
        select(
            func.count().label("total"),
            func.count().filter(ApiLog.status == "success").label("successful"),
            func.count().filter(ApiLog.status != "success").label("failed"),
            func.avg(ApiLog.duration_ms).label("avg_latency"),
            func.sum(ApiLog.tokens_used).label("total_tokens"),
        ).where(and_(ApiLog.service == "claude", ApiLog.created_at >= day_ago))
    )
    row = result.one()

    last_success = await db.execute(
        select(ApiLog.created_at)
        .where(and_(ApiLog.service == "claude", ApiLog.status == "success"))
        .order_by(ApiLog.created_at.desc())
        .limit(1)
    )
    last_success_at = last_success.scalar_one_or_none()

    last_error_result = await db.execute(
        select(ApiLog.error_message, ApiLog.created_at)
        .where(and_(ApiLog.service == "claude", ApiLog.status != "success"))
        .order_by(ApiLog.created_at.desc())
        .limit(1)
    )
    last_error_row = last_error_result.one_or_none()

    return {
        "calls_24h": row.total or 0,
        "successful_24h": row.successful or 0,
        "failed_24h": row.failed or 0,
        "avg_latency_ms": round(row.avg_latency) if row.avg_latency else 0,
        "total_tokens_24h": row.total_tokens or 0,
        "last_success_at": last_success_at.isoformat() if last_success_at else None,
        "last_error": last_error_row.error_message if last_error_row else None,
        "last_error_at": last_error_row.created_at.isoformat() if last_error_row else None,
    }
