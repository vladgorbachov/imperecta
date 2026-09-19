"""Edge-cacheable public reads (stale-while-revalidate architecture, 2026-09-19).

Storefront data (pool, market KPIs) is identical for every anonymous
visitor, so the CDN in front of the API serves it from the edge: the origin
answers one request per cache key per ``s-maxage`` window and the viewer
gets a stale-but-instant page that the CDN revalidates in the background.

Two rules keep the cache safe:

* Only ANONYMOUS responses are ``public``. A request carrying a Bearer
  token may be personalised (superusers see blocked countries), so it is
  marked ``private`` and never enters the shared cache. The frontend sends
  no Authorization header on public reads for exactly this reason.
* A bad or expired token on a public route degrades to anonymous instead
  of 401: public routes never bounce a viewer, and the CDN never caches a
  401 in place of data.

``ETag`` + ``If-None-Match`` (304) are added by :class:`PublicETagMiddleware`
for every ``public`` GET so browsers and the CDN revalidate for free.
"""

from __future__ import annotations

import hashlib
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response as StarletteResponse

from app.common.deps import get_current_user, security
from app.database import get_db
from app.models.core import User

# 5-minute snapshots at the edge, served stale for a further 10 minutes
# while the CDN refreshes them in the background.
PUBLIC_S_MAXAGE_SEC = 300
PUBLIC_STALE_WHILE_REVALIDATE_SEC = 600
PUBLIC_CACHE_CONTROL = (
    f"public, s-maxage={PUBLIC_S_MAXAGE_SEC}, "
    f"stale-while-revalidate={PUBLIC_STALE_WHILE_REVALIDATE_SEC}"
)
PRIVATE_CACHE_CONTROL = "private, no-store"


async def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User | None:
    """User when a valid Bearer token is present; None otherwise (no DB hit)."""
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


async def public_cache(
    response: Response,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> None:
    """Route dependency: stamp Cache-Control by request anonymity."""
    response.headers["Cache-Control"] = (
        PRIVATE_CACHE_CONTROL if credentials is not None else PUBLIC_CACHE_CONTROL
    )


PublicCache = Annotated[None, Depends(public_cache)]


class PublicETagMiddleware(BaseHTTPMiddleware):
    """ETag/304 for public GET responses (body-hash; cheap at storefront sizes)."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> StarletteResponse:
        response = await call_next(request)
        if request.method != "GET" or response.status_code != 200:
            return response
        if not response.headers.get("cache-control", "").startswith("public"):
            return response
        body = b"".join([chunk async for chunk in response.body_iterator])
        etag = f'W/"{hashlib.sha1(body).hexdigest()[:32]}"'  # noqa: S324 - not security
        headers = dict(response.headers)
        headers.pop("content-length", None)
        headers["etag"] = etag
        if request.headers.get("if-none-match") == etag:
            return StarletteResponse(status_code=304, headers=headers)
        return StarletteResponse(
            content=body,
            status_code=200,
            headers=headers,
            media_type=response.media_type,
        )
