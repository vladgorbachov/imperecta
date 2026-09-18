"""Taxonomy enrichment tick (P13): budget-capped Claude batches via beat.

Every tick translates a slice of untranslated categories and classifies a
slice of untyped products (priced-first ordering — what the storefront
shows). Bounded LLM spend per tick; the queue self-drains over hours, new
products picked up on later ticks. acks_late like the other idempotent
long tasks: a redelivered tick just processes the next slice.
"""

from __future__ import annotations

import structlog
from anthropic import Anthropic

from app.config import Settings
from app.observability.sentry_init import capture_exception_if_initialized
from app.workers.celery_app import celery_app

slog = structlog.get_logger(__name__)

# Per-tick budget: at most 1 category batch + N product batches of LLM calls.
PRODUCT_BATCHES_PER_TICK = 8
# Free duplicate-copy pass cap per tick (DB writes only, zero LLM spend).
REUSE_ROWS_PER_TICK = 500
ENRICH_MODEL_FALLBACK = "claude-haiku-4-5-20251001"


def _resolve_model_sync(settings: Settings) -> str:
    """Cheapest-family model id; fixed fallback when resolution fails."""
    import asyncio

    from app.modules.ai_analyst.claude_client import resolve_claude_model

    try:
        return asyncio.run(resolve_claude_model("auto:haiku", settings.claude_api_key))
    except Exception as exc:  # noqa: BLE001 - resolver outage must not stop enrichment
        capture_exception_if_initialized(exc)
        return ENRICH_MODEL_FALLBACK


def _complete(client: Anthropic, model: str, prompt: str) -> str:
    from app.modules.enrichment.taxonomy import ENRICH_MAX_TOKENS

    response = client.messages.create(
        model=model,
        max_tokens=ENRICH_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text if response.content else ""


@celery_app.task(name="taxonomy_enrich_tick", bind=True, acks_late=True)
def taxonomy_enrich_tick(self) -> dict:
    """One budget-capped enrichment slice; safe to run every tick."""
    from app.modules.enrichment import taxonomy as tx

    settings = Settings()
    if not settings.claude_api_key:
        return {"status": "no_api_key"}

    client = Anthropic(api_key=settings.claude_api_key)
    model = _resolve_model_sync(settings)
    categories_written = products_written = reused = 0

    try:
        # Free pass first: identical products inherit existing enrichment
        # (user rule: never spend AI credits on a name already answered).
        reused = tx.reuse_existing_enrichment_sync(REUSE_ROWS_PER_TICK)

        pending = tx.fetch_untranslated_categories_sync(tx.CATEGORY_BATCH_SIZE)
        if pending:
            names_by_index = {str(i): name for i, (_, name) in enumerate(pending)}
            reply = _complete(client, model, tx.build_category_prompt(names_by_index))
            translated = tx.parse_category_reply(reply, names_by_index)
            updates = {
                pending[int(idx)][0]: name_en for idx, name_en in translated.items()
            }
            categories_written = tx.write_category_translations_sync(updates)

        for _ in range(PRODUCT_BATCHES_PER_TICK):
            batch = tx.fetch_untyped_products_sync(tx.PRODUCT_BATCH_SIZE)
            if not batch:
                break
            titles_by_index = {str(i): name for i, (_, name) in enumerate(batch)}
            reply = _complete(client, model, tx.build_product_prompt(titles_by_index))
            classified = tx.parse_product_reply(reply, titles_by_index)
            updates = {
                batch[int(idx)][0]: columns for idx, columns in classified.items()
            }
            written = tx.write_product_types_sync(updates)
            products_written += written
            if written == 0:
                # The model answered nothing usable for this slice — the same
                # rows would be re-fetched forever; stop and let the next tick
                # (fresh model call) retry instead of burning the budget now.
                break
    except Exception as exc:
        capture_exception_if_initialized(exc)
        slog.error("taxonomy_enrich_failed", error=str(exc)[:500])
        return {
            "status": f"error:{type(exc).__name__}",
            "categories_written": categories_written,
            "products_written": products_written,
        }

    summary = {
        "status": "completed",
        "model": model,
        "reused": reused,
        "categories_written": categories_written,
        "products_written": products_written,
    }
    slog.info("taxonomy_enrich_done", **summary)
    return summary
