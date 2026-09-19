"""News API — external headlines feed (no DB / gate)."""

from fastapi import APIRouter, Query

from app.common.deps import CurrentUser
from app.modules.news import service as news_service
from app.modules.news.schemas import NewsResponse

router = APIRouter(prefix="/news", tags=["news"])


@router.get("", response_model=NewsResponse)
async def get_market_news(
    _current_user: CurrentUser,
    country_code: str | None = Query(default=None, min_length=2, max_length=2),
    language: str = Query(default="en", min_length=2, max_length=5),
) -> NewsResponse:
    """Return retail/business headlines from the provider chain."""
    return await news_service.get_news(
        country_code=country_code.upper() if country_code else None,
        language=language,
    )
