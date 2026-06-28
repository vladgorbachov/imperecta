"""Single decision point for is_superuser privilege writes (extensible for future 2FA)."""

from __future__ import annotations

from typing import Any

_ADMIN_SUPERUSER_KINDS: frozenset[str] = frozenset({"admin_create", "admin_update"})


def may_set_superuser(*, kind: str, target_fields: dict[str, Any]) -> bool:
    """Return whether this operation kind may carry ``is_superuser`` in *target_fields*.

    Current rule (seam 1): only explicit admin kinds (``admin_create``, ``admin_update``).

    Future 2FA seam: extend this function to require all 2FA verification flags on
    *target_fields* when ``is_superuser`` is True — no door rewrite required.
    """
    if kind not in _ADMIN_SUPERUSER_KINDS:
        return False
    # Future: when target_fields.get("is_superuser") is True:
    #     return all(target_fields.get(flag) is True for flag in TWO_FA_FLAGS)
    return True
