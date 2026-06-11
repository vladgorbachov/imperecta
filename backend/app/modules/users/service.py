"""Users service: self-profile + plan-limits (UsersService) and admin user
CRUD with byte-preserved security invariants (UsersAdminService).

CORE-USERS1 lifted these out of:
    - app.modules.core.api_auth (_build_user_response, _plan_str,
      ALLOWED_USER_UPDATE_FIELDS) -> UsersService
    - app.modules.core.plans.service (get_product_limit, get_competitor_limit,
      is_free_plan; the package had zero importers) -> UsersService
    - app.modules.admin.parsing_admin.ParsingAdminService (8 user-CRUD methods
      + 4 validators) -> UsersAdminService
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.validation import validate_language
from app.entitlements import get_entitlements_for_frontend, get_limit, get_service_tier
from app.entitlements.plan import ServiceTier, UserPlan
from app.models.core import User, UserProduct
from app.modules.auth.service import hash_password
from app.modules.users.schemas import UserResponse

# /me whitelist: fields the self-profile PUT route is allowed to mutate.
# Everything else in UserUpdate is silently dropped (e.g. trying to PUT
# is_superuser or email through /users/me must not succeed).
ALLOWED_USER_UPDATE_FIELDS: frozenset[str] = frozenset(
    {
        "name",
        "company_name",
        "language",
        "timezone",
        "ai_tone",
        "default_currency",
        "avatar_url",
        "preferences",
    }
)

# Admin user-CRUD list cap; same as the pre-CORE-USERS1 default.
USERS_DETAILED_MAX_LIMIT: int = 2000


def get_product_limit(plan: UserPlan) -> int:
    """Max products allowed for plan (delegates to entitlements)."""
    return get_limit(plan, "products")


def get_competitor_limit(plan: UserPlan) -> int:
    """Max competitors allowed for plan (delegates to entitlements)."""
    return get_limit(plan, "competitors")


def is_free_plan(plan: UserPlan) -> bool:
    """True if plan has product-limit enforcement (Free service tier)."""
    return get_service_tier(plan) == ServiceTier.FREE


def _plan_str(plan: object) -> str:
    return plan.value if hasattr(plan, "value") else str(plan)


def _to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat()


class UsersService:
    """Self-profile read/update for the /users/me routes."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def build_user_response(current_user: User) -> UserResponse:
        """Wrap a User ORM row in the public UserResponse contract (matches
        the pre-CORE-USERS1 /auth/me payload byte-for-byte)."""
        return UserResponse(
            id=current_user.id,
            email=current_user.email,
            name=current_user.name,
            company_name=current_user.company_name,
            plan=_plan_str(current_user.plan),
            trial_ends_at=current_user.trial_ends_at,
            language=current_user.language,
            timezone=getattr(current_user, "timezone", None),
            ai_tone=getattr(current_user, "ai_tone", None),
            default_currency=getattr(current_user, "default_currency", None),
            is_superuser=getattr(current_user, "is_superuser", None),
            is_active=getattr(current_user, "is_active", None),
            created_at=current_user.created_at,
            last_login_at=getattr(current_user, "last_login_at", None),
            telegram_chat_id=current_user.telegram_chat_id,
            avatar_url=getattr(current_user, "avatar_url", None),
            preferences=getattr(current_user, "preferences", None),
            entitlements=get_entitlements_for_frontend(
                current_user.plan, trial_ends_at=current_user.trial_ends_at
            ),
        )

    async def update_me(self, current_user: User, patch: dict[str, Any]) -> UserResponse:
        """Apply ALLOWED_USER_UPDATE_FIELDS only; treat avatar_url='' as
        explicit clear (preserves the pre-CORE-USERS1 behavior)."""
        for key, value in patch.items():
            if key not in ALLOWED_USER_UPDATE_FIELDS:
                continue
            if key == "avatar_url" and value == "":
                value = None
            setattr(current_user, key, value)
        await self.db.flush()
        return self.build_user_response(current_user)


class UsersAdminService:
    """Admin user CRUD for /admin/users/* routes.

    SECURITY INVARIANTS (verified byte-preserved from the
    ParsingAdminService source):
        - cannot deactivate own account
        - cannot deactivate the last active superuser
        - cannot remove own superuser role
        - cannot remove the role from the last superuser
        - cannot delete own account
        - cannot delete the last superuser
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_users_detailed(self, limit: int = 500) -> list[dict[str, Any]]:
        """Detailed users list for admin diagnostics tab."""
        safe_limit = max(1, min(limit, USERS_DETAILED_MAX_LIMIT))
        stmt = (
            select(
                User.id,
                User.email,
                User.name,
                User.company_name,
                User.plan,
                User.is_active,
                User.is_superuser,
                User.language,
                User.timezone,
                User.login_count,
                User.last_login_at,
                User.created_at,
                func.count(UserProduct.id).label("tracked_products"),
            )
            .outerjoin(UserProduct, UserProduct.user_id == User.id)
            .group_by(User.id)
            .order_by(User.created_at.desc())
            .limit(safe_limit)
        )
        result = await self.db.execute(stmt)
        rows = result.mappings().all()
        return [
            {
                "id": str(row["id"]),
                "email": row["email"],
                "name": row["name"],
                "company_name": row["company_name"],
                "plan": row["plan"],
                "is_active": bool(row["is_active"]),
                "is_superuser": bool(row["is_superuser"]),
                "language": row["language"],
                "timezone": row["timezone"],
                "login_count": int(row["login_count"] or 0),
                "tracked_products": int(row["tracked_products"] or 0),
                "last_login_at": _to_iso(row["last_login_at"]),
                "created_at": _to_iso(row["created_at"]),
            }
            for row in rows
        ]

    async def create_user(
        self,
        *,
        email: str,
        password: str,
        name: str | None,
        company_name: str | None,
        plan: str,
        language: str,
        timezone: str | None,
        is_active: bool,
        is_superuser: bool,
    ) -> dict[str, Any]:
        """Create user from admin panel."""
        normalized_email = email.strip().lower()
        if not normalized_email:
            raise ValueError("Email is required")
        existing = await self.db.scalar(select(User.id).where(User.email == normalized_email))
        if existing is not None:
            raise ValueError("Email already registered")
        validated_plan = self._validate_plan(plan)
        validated_language = self._validate_language(language)
        validated_timezone = self._normalize_timezone(timezone)
        user = User(
            email=normalized_email,
            password_hash=hash_password(password),
            name=self._normalize_optional_text(name),
            company_name=self._normalize_optional_text(company_name),
            plan=validated_plan,
            language=validated_language,
            timezone=validated_timezone,
            is_active=is_active,
            is_superuser=is_superuser,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return await self.get_user_detailed(user.id)

    async def get_user_detailed(self, user_id: UUID) -> dict[str, Any]:
        """Return single user in Users Management contract."""
        stmt = (
            select(
                User.id,
                User.email,
                User.name,
                User.company_name,
                User.plan,
                User.is_active,
                User.is_superuser,
                User.language,
                User.timezone,
                User.login_count,
                User.last_login_at,
                User.created_at,
                func.count(UserProduct.id).label("tracked_products"),
            )
            .outerjoin(UserProduct, UserProduct.user_id == User.id)
            .where(User.id == user_id)
            .group_by(User.id)
            .limit(1)
        )
        result = await self.db.execute(stmt)
        row = result.mappings().first()
        if row is None:
            raise ValueError(f"User not found: {user_id}")
        return {
            "id": str(row["id"]),
            "email": row["email"],
            "name": row["name"],
            "company_name": row["company_name"],
            "plan": row["plan"],
            "is_active": bool(row["is_active"]),
            "is_superuser": bool(row["is_superuser"]),
            "language": row["language"],
            "timezone": row["timezone"],
            "login_count": int(row["login_count"] or 0),
            "tracked_products": int(row["tracked_products"] or 0),
            "last_login_at": _to_iso(row["last_login_at"]),
            "created_at": _to_iso(row["created_at"]),
        }

    async def update_user(
        self,
        user_id: UUID,
        *,
        email: str | None = None,
        name: str | None = None,
        company_name: str | None = None,
        plan: str | None = None,
        language: str | None = None,
        timezone: str | None = None,
        is_active: bool | None = None,
        is_superuser: bool | None = None,
    ) -> dict[str, Any]:
        """Update mutable user fields from admin panel."""
        user = await self.db.get(User, user_id)
        if user is None:
            raise ValueError(f"User not found: {user_id}")
        if email is not None:
            normalized_email = email.strip().lower()
            if not normalized_email:
                raise ValueError("Email cannot be empty")
            existing = await self.db.scalar(
                select(User.id).where(User.email == normalized_email, User.id != user_id)
            )
            if existing is not None:
                raise ValueError("Email already registered")
            user.email = normalized_email
        if name is not None:
            user.name = self._normalize_optional_text(name)
        if company_name is not None:
            user.company_name = self._normalize_optional_text(company_name)
        if plan is not None:
            user.plan = self._validate_plan(plan)
        if language is not None:
            user.language = self._validate_language(language)
        if timezone is not None:
            user.timezone = self._normalize_timezone(timezone)
        if is_active is not None:
            user.is_active = bool(is_active)
        if is_superuser is not None:
            user.is_superuser = bool(is_superuser)
        await self.db.commit()
        return await self.get_user_detailed(user_id)

    async def set_user_active(
        self,
        user_id: UUID,
        *,
        is_active: bool,
        actor_user_id: UUID,
    ) -> dict[str, Any]:
        """Activate or deactivate user with safety checks.

        SECURITY:
            - rejects self-deactivation,
            - rejects deactivation of the LAST active superuser.
        """
        if not is_active and user_id == actor_user_id:
            raise ValueError("You cannot deactivate your own account")
        user = await self.db.get(User, user_id)
        if user is None:
            raise ValueError(f"User not found: {user_id}")
        if not is_active and user.is_superuser:
            superusers_count = await self.db.scalar(
                select(func.count(User.id)).where(
                    User.is_superuser.is_(True), User.is_active.is_(True)
                )
            )
            if int(superusers_count or 0) <= 1:
                raise ValueError("Cannot deactivate the last active superuser")
        user.is_active = is_active
        await self.db.commit()
        return await self.get_user_detailed(user_id)

    async def set_user_superuser(
        self,
        user_id: UUID,
        *,
        is_superuser: bool,
        actor_user_id: UUID,
    ) -> dict[str, Any]:
        """Grant or revoke superuser role with safety checks.

        SECURITY:
            - rejects self-demotion (removing own superuser role),
            - rejects role-removal from the LAST superuser.
        """
        if not is_superuser and user_id == actor_user_id:
            raise ValueError("You cannot remove your own superuser role")
        user = await self.db.get(User, user_id)
        if user is None:
            raise ValueError(f"User not found: {user_id}")
        if not is_superuser and user.is_superuser:
            superusers_count = await self.db.scalar(
                select(func.count(User.id)).where(User.is_superuser.is_(True))
            )
            if int(superusers_count or 0) <= 1:
                raise ValueError("Cannot remove role from the last superuser")
        user.is_superuser = is_superuser
        await self.db.commit()
        return await self.get_user_detailed(user_id)

    async def reset_user_password(
        self,
        user_id: UUID,
        *,
        new_password: str,
        force_password_change: bool,
    ) -> dict[str, Any]:
        """Admin password reset action."""
        user = await self.db.get(User, user_id)
        if user is None:
            raise ValueError(f"User not found: {user_id}")
        user.password_hash = hash_password(new_password)
        user.force_password_change = force_password_change
        await self.db.commit()
        return await self.get_user_detailed(user_id)

    async def delete_user(self, user_id: UUID, *, actor_user_id: UUID) -> None:
        """Delete user with safety checks.

        SECURITY:
            - rejects self-delete,
            - rejects deletion of the LAST superuser.
        """
        if user_id == actor_user_id:
            raise ValueError("You cannot delete your own account")
        user = await self.db.get(User, user_id)
        if user is None:
            raise ValueError(f"User not found: {user_id}")
        if user.is_superuser:
            superusers_count = await self.db.scalar(
                select(func.count(User.id)).where(User.is_superuser.is_(True))
            )
            if int(superusers_count or 0) <= 1:
                raise ValueError("Cannot delete the last superuser")
        await self.db.delete(user)
        await self.db.commit()

    # ---- validators (local; language reuses common/validation) -----------

    @staticmethod
    def _validate_plan(value: str) -> str:
        normalized = (value or "").strip().lower()
        try:
            return UserPlan(normalized).value
        except ValueError as exc:
            raise ValueError(
                "Invalid plan. Allowed: trial, starter, business, pro, enterprise"
            ) from exc

    @staticmethod
    def _validate_language(value: str) -> str:
        normalized = (value or "").strip().lower()
        return validate_language(normalized)

    @staticmethod
    def _normalize_timezone(value: str | None) -> str:
        normalized = (value or "UTC").strip()
        if not normalized:
            return "UTC"
        if len(normalized) > 50:
            raise ValueError("Timezone exceeds maximum length (50)")
        return normalized

    @staticmethod
    def _normalize_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None
