"""P7/P11: namespaced UI preferences and favorites inside users.preferences."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.main import app
from app.modules.users.service import UsersService


def _user(preferences=None):
    return SimpleNamespace(id=uuid4(), preferences=preferences)


@pytest.mark.asyncio
async def test_put_namespace_preserves_other_keys():
    user = _user({"dashboard": {"legacy": 1}, "favorites": {"listing_ids": ["a"]}})
    db = MagicMock()
    db.refresh = AsyncMock()
    svc = UsersService(db)
    with patch(
        "app.modules.users.service.write_user_async",
        new=AsyncMock(return_value=SimpleNamespace(ok=True)),
    ) as wu:
        blob = await svc.put_preferences_namespace(user, "ui", {"products_density": "compact"})
    assert blob == {"products_density": "compact"}
    written = wu.call_args.kwargs["fields"]["preferences"]
    assert written["dashboard"] == {"legacy": 1}
    assert written["favorites"] == {"listing_ids": ["a"]}
    assert written["ui"] == {"products_density": "compact"}
    assert wu.call_args.kwargs["kind"] == "self_update"


@pytest.mark.asyncio
async def test_get_namespace_handles_unset_and_garbage():
    svc = UsersService(MagicMock())
    assert await svc.get_preferences_namespace(_user(None), "ui") == {}
    assert await svc.get_preferences_namespace(_user({"ui": "not-a-dict"}), "ui") == {}
    assert await svc.get_preferences_namespace(_user({"ui": {"a": 1}}), "ui") == {"a": 1}


@pytest.mark.asyncio
async def test_put_namespace_gate_failure_raises():
    user = _user({})
    db = MagicMock()
    svc = UsersService(db)
    with patch(
        "app.modules.users.service.write_user_async",
        new=AsyncMock(return_value=SimpleNamespace(ok=False)),
    ):
        with pytest.raises(ValueError):
            await svc.put_preferences_namespace(user, "ui", {})


def test_routes_registered():
    schema = app.openapi()
    for path, method in (
        ("/api/users/me/preferences", "get"),
        ("/api/users/me/preferences", "put"),
        ("/api/users/me/favorites", "get"),
        ("/api/users/me/favorites", "put"),
    ):
        assert method in schema["paths"].get(path, {}), f"{method.upper()} {path} missing"
