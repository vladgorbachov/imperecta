"""Starlette-1.x-safe route iteration for contract tests.

Since starlette 1.0, ``app.routes`` returns lazy ``_IncludedRouter``
entries for routers mounted via ``include_router`` instead of flattened
``APIRoute`` objects — iterating paths off ``app.routes`` directly sees
only the app's own routes (/health, /docs), so presence asserts fail and
absence asserts pass vacuously. Every test that inspects routes must go
through this helper.

The yielded object for an included route is a thin proxy: ``.path``
carries the include prefix applied; every other attribute (methods,
endpoint, response_model, name, ...) delegates to the real APIRoute.
``isinstance(route, APIRoute)`` checks do NOT survive the proxy — filter
with ``getattr(route, "methods", None)`` instead.
"""

from __future__ import annotations

from typing import Any, Iterator


class PrefixedRoute:
    """Proxy over an APIRoute with the router-include prefix applied."""

    __slots__ = ("_route", "path")

    def __init__(self, route: Any, prefix: str) -> None:
        object.__setattr__(self, "_route", route)
        object.__setattr__(self, "path", prefix + getattr(route, "path", ""))

    def __getattr__(self, name: str) -> Any:
        return getattr(object.__getattribute__(self, "_route"), name)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"PrefixedRoute({self.path!r})"


def iter_app_routes(app: Any) -> Iterator[Any]:
    """Yield route-like objects (.path/.methods/...), include-prefixes applied."""
    for route in app.routes:
        if type(route).__name__ == "_IncludedRouter":
            prefix = getattr(route.include_context, "prefix", "") or ""
            for sub in route.original_router.routes:
                yield PrefixedRoute(sub, prefix)
        else:
            yield route


def registered_paths(app: Any) -> set[str]:
    """All registered paths, prefixes applied."""
    return {getattr(route, "path", "") for route in iter_app_routes(app)}
