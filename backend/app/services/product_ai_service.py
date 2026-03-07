"""AI service for product categorization and price recommendations."""

import json
import logging
import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import CompetitorProduct, Product

logger = logging.getLogger(__name__)
settings = Settings()


async def auto_categorize(products: list[dict]) -> list[dict]:
    """
    AI auto-categorization for product list. Returns list with suggested_category per item.
    Falls back to empty suggested_category if Claude unavailable.
    """
    if not products:
        return []

    if not settings.claude_api_key:
        logger.warning("CLAUDE_API_KEY not set, skipping auto-categorize")
        return [{**p, "suggested_category": None} for p in products]

    try:
        import anthropic

        items = [{"name": p.get("name", ""), "sku": p.get("sku", ""), "price": str(p.get("price", ""))} for p in products]
        prompt = f"""Given these e-commerce products, suggest a short category name (1-3 words) for each.
Respond with JSON array: [{{"index": 0, "suggested_category": "..."}}, ...]
Products: {json.dumps(items, ensure_ascii=False)}"""

        client = anthropic.AsyncAnthropic(api_key=settings.claude_api_key)
        response = await client.messages.create(
            model=settings.claude_model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text if response.content else "[]"
        match = re.search(r"\[[\s\S]*\]", text)
        suggestions = json.loads(match.group()) if match else []
        by_idx = {
            s["index"]: s.get("suggested_category")
            for s in suggestions
            if isinstance(s, dict)
        }
        return [
            {**p, "suggested_category": by_idx.get(i)}
            for i, p in enumerate(products)
        ]
    except Exception as e:
        logger.warning("auto_categorize failed: %s", e)
        return [{**p, "suggested_category": None} for p in products]


async def get_price_recommendation(
    db: AsyncSession,
    product_id: UUID,
    user_id: UUID,
) -> dict:
    """
    AI price recommendation for a product based on competitor prices.
    Returns dict with recommended_price, reasoning, confidence.
    """
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.user_id == user_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise ValueError("Product not found")
    my_price = float(product.current_price) if product.current_price else 0

    cp_result = await db.execute(
        select(CompetitorProduct.last_price)
        .join(Product, CompetitorProduct.product_id == Product.id)
        .where(
            CompetitorProduct.product_id == product_id,
            Product.user_id == user_id,
            CompetitorProduct.is_active.is_(True),
        )
    )
    competitor_prices = [float(r[0]) for r in cp_result.all() if r[0] is not None]

    if not settings.claude_api_key:
        avg = sum(competitor_prices) / len(competitor_prices) if competitor_prices else my_price
        return {"recommended_price": round(avg, 2), "reasoning": "Fallback: competitor average.", "confidence": 0.5}

    try:
        import anthropic

        context = {"my_price": my_price, "competitor_prices": competitor_prices, "product_name": product.name}
        prompt = f"""Suggest optimal price for e-commerce product. JSON: {{"recommended_price": N, "reasoning": "...", "confidence": 0.0-1.0}}
Context: {json.dumps(context, ensure_ascii=False)}"""

        client = anthropic.AsyncAnthropic(api_key=settings.claude_api_key)
        response = await client.messages.create(
            model=settings.claude_model,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text if response.content else "{}"
        match = re.search(r"\{[^{}]*\}", text)
        parsed = json.loads(match.group()) if match else {}
        return {
            "recommended_price": parsed.get("recommended_price", my_price),
            "reasoning": parsed.get("reasoning", ""),
            "confidence": float(parsed.get("confidence", 0.5)),
        }
    except Exception as e:
        logger.warning("get_price_recommendation failed: %s", e)
        avg = sum(competitor_prices) / len(competitor_prices) if competitor_prices else my_price
        return {"recommended_price": round(avg, 2), "reasoning": str(e), "confidence": 0.3}
