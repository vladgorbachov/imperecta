"""Single decision point for is_active writes (reactivation abolished for users)."""

from __future__ import annotations

from typing import Any

_ADMIN_DEACTIVATE_KIND: str = "admin_update"


def may_set_active(*, kind: str, target_fields: dict[str, Any]) -> bool:
    """Return whether ``is_active`` in *target_fields* is permitted for *kind*.

    Current rule (mirrors listing reactivation-abolished):
        - ``is_active=True`` → never (all kinds rejected at door)
        - ``is_active=False`` → only ``admin_update`` (deactivation)
        - absent → permitted (predicate does not apply)

    ``admin_create`` does not carry ``is_active``; new users are active via DB default.
    """
    if "is_active" not in target_fields:
        return True
    value = target_fields["is_active"]
    if value is True:
        return False
    if value is False:
        return kind == _ADMIN_DEACTIVATE_KIND
    return False
