"""AI service for alert event explanations and recommendations."""

import json
import logging
import re
import time

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.models import Alert, AlertEvent, Competitor, CompetitorProduct, Product

logger = logging.getLogger(__name__)
settings = Settings()

ALERT_EXPLANATION_PROMPT = """You are a competitive intelligence analyst. Write in Russian.
Given a price alert event (product, competitor, old/new price), provide:
1. Brief explanation of what happened and why it might matter
2. Recommendation (1-2 sentences) for the merchant
3. Optional: recommended price (number only, no currency) if relevant

Respond in JSON: {"explanation": "...", "recommendation": "...", "recommended_price": null or number}
Keep it concise (2-4 sentences total)."""


async def _log_api_call(
    db: AsyncSession,
    service: str,
    status: str,
    duration_ms: int,
    *,
    error: str | None = None,
    tokens: int | None = None,
) -> None:
    """Log external API call to api_logs table."""
    from app.models.api_log import ApiLog

    log = ApiLog(
        service=service,
        endpoint="alert_explanation",
        status=status,
        duration_ms=duration_ms,
        error_message=error,
        tokens_used=tokens,
    )
    db.add(log)


async def generate_alert_explanation(
    db: AsyncSession,
    alert_event_id: int,
) -> dict:
    """
    Generate AI explanation for alert event. Updates event with ai_explanation, ai_recommendation, ai_recommended_price.
    Returns dict with explanation, recommendation, recommended_price.
    """
    result = await db.execute(
        select(AlertEvent)
        .options(
            selectinload(AlertEvent.alert),
            selectinload(AlertEvent.competitor_product).selectinload(CompetitorProduct.competitor),
            selectinload(AlertEvent.competitor_product).selectinload(CompetitorProduct.product),
        )
        .where(AlertEvent.id == alert_event_id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise ValueError("Alert event not found")

    product = None
    competitor = None
    if event.competitor_product:
        product = event.competitor_product.product
        competitor = event.competitor_product.competitor
    if not product and event.alert and event.alert.product_id:
        prod_result = await db.execute(
            select(Product).where(Product.id == event.alert.product_id)
        )
        product = prod_result.scalar_one_or_none()
    product_name = product.name if product else "Product"
    competitor_name = competitor.name if competitor else "Competitor"
    old_p = float(event.old_price) if event.old_price else 0
    new_p = float(event.new_price) if event.new_price else 0
    change_pct = (
        ((new_p - old_p) / old_p * 100) if old_p and old_p > 0 else 0
    )

    context = {
        "product": product_name,
        "competitor": competitor_name,
        "old_price": old_p,
        "new_price": new_p,
        "change_percent": round(change_pct, 1),
        "message": event.message,
    }

    if not settings.claude_api_key:
        logger.warning("CLAUDE_API_KEY not set, skipping alert explanation")
        fallback = f"Изменение цены на {change_pct:.1f}%: {old_p} → {new_p}."
        event.ai_explanation = fallback
        event.ai_recommendation = None
        event.ai_recommended_price = None
        return {"explanation": fallback, "recommendation": None, "recommended_price": None}

    start = time.time()
    try:
        client = anthropic.AsyncAnthropic(api_key=settings.claude_api_key)
        response = await client.messages.create(
            model=settings.claude_model,
            max_tokens=512,
            system=ALERT_EXPLANATION_PROMPT,
            messages=[{"role": "user", "content": json.dumps(context, ensure_ascii=False)}],
        )
        duration_ms = int((time.time() - start) * 1000)
        tokens = 0
        if response.usage:
            tokens = (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0)
        await _log_api_call(db, "claude", "success", duration_ms, tokens=tokens)

        text = response.content[0].text if response.content else ""
        parsed = _parse_json_response(text)
        explanation = parsed.get("explanation") or ""
        recommendation = parsed.get("recommendation")
        rec_price = parsed.get("recommended_price")

        event.ai_explanation = explanation
        event.ai_recommendation = recommendation
        event.ai_recommended_price = (
            float(rec_price) if rec_price is not None else None
        )

        return {
            "explanation": explanation,
            "recommendation": recommendation,
            "recommended_price": event.ai_recommended_price,
        }
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        await _log_api_call(db, "claude", "error", duration_ms, error=str(e))
        logger.warning("Alert explanation failed: %s", e)
        raise


def _parse_json_response(text: str) -> dict:
    """Extract JSON from model response."""
    text = text.strip()
    match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {"explanation": text, "recommendation": None, "recommended_price": None}


async def generate_auto_response(db: AsyncSession, alert_event_id: int) -> dict:
    """
    Generate auto-response: recommended price for alert event.
    Returns dict with recommended_price, reasoning, expected_impact.
    """
    result = await db.execute(
        select(AlertEvent)
        .options(
            selectinload(AlertEvent.alert),
            selectinload(AlertEvent.competitor_product).selectinload(CompetitorProduct.product),
        )
        .where(AlertEvent.id == alert_event_id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise ValueError("Alert event not found")

    product = event.competitor_product.product if event.competitor_product else None
    if not product and event.alert and event.alert.product_id:
        prod_result = await db.execute(
            select(Product).where(Product.id == event.alert.product_id)
        )
        product = prod_result.scalar_one_or_none()
    old_p = float(event.old_price) if event.old_price else 0
    new_p = float(event.new_price) if event.new_price else 0

    if not settings.claude_api_key:
        mid = (old_p + new_p) / 2 if old_p and new_p else new_p
        return {
            "recommended_price": round(mid, 2),
            "reasoning": "Fallback: midpoint between old and new price.",
            "expected_impact": "",
        }

    product_name = product.name if product else "Product"
    context = {
        "product": product_name,
        "old_price": old_p,
        "new_price": new_p,
        "message": event.message,
    }
    prompt = f"""Given price change: {json.dumps(context, ensure_ascii=False)}
Suggest a recommended price (number) and brief reasoning. JSON: {{"recommended_price": N, "reasoning": "...", "expected_impact": "..."}}"""

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.claude_api_key)
        response = await client.messages.create(
            model=settings.claude_model,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text if response.content else ""
        parsed = _parse_json_response(text)
        return {
            "recommended_price": parsed.get("recommended_price"),
            "reasoning": parsed.get("reasoning", ""),
            "expected_impact": parsed.get("expected_impact", ""),
        }
    except Exception as e:
        logger.warning("Auto-response failed: %s", e)
        raise
