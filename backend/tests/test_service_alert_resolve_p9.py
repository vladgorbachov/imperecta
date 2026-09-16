"""P9 resolve service alert: gate allowlist, route, strict field set (no DB)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.main import app
from app.modules.admin import alerts_admin_write
from app.modules.persist.writer import SUPPORTED_WRITE_OPERATIONS


def test_writer_allows_service_alerts_update():
    assert SUPPORTED_WRITE_OPERATIONS["service_alerts"] == frozenset(
        {"insert", "update", "retention_delete"}
    )


def test_patch_route_registered():
    schema = app.openapi()
    entry = schema["paths"].get("/api/admin/service_alerts/{alert_id}", {})
    assert "patch" in entry, sorted(schema["paths"])


def test_migration_050_widens_only_service_alerts():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "050_service_alerts_update.py"
    ).read_text(encoding="utf-8")
    widened = (
        "WHEN 'service_alerts' THEN RETURN p_operation IN "
        "('insert', 'update', 'retention_delete');"
    )
    narrowed = (
        "WHEN 'service_alerts' THEN RETURN p_operation IN ('insert', 'retention_delete');"
    )
    assert widened in source  # upgrade branch
    assert narrowed in source  # downgrade replacement target


class TestResolveSemantics:
    def _db_returning(self, row):
        db = MagicMock()
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = row
        db.execute = AsyncMock(return_value=execute_result)
        return db

    @pytest.mark.asyncio
    async def test_unknown_id_returns_none_without_write(self):
        db = self._db_returning(None)
        with patch.object(alerts_admin_write, "write_meta_async") as write:
            out = await alerts_admin_write.resolve_service_alert(db, uuid4())
        assert out is None
        write.assert_not_called()

    @pytest.mark.asyncio
    async def test_already_resolved_is_noop(self):
        row = MagicMock(resolved_at=datetime.now(timezone.utc))
        db = self._db_returning(row)
        with patch.object(alerts_admin_write, "write_meta_async") as write:
            out = await alerts_admin_write.resolve_service_alert(db, uuid4())
        assert out is row
        write.assert_not_called()

    @pytest.mark.asyncio
    async def test_open_alert_writes_strict_field_set(self):
        row = MagicMock(resolved_at=None)
        db = self._db_returning(row)
        alert_id = uuid4()
        with patch.object(
            alerts_admin_write,
            "write_meta_async",
            new=AsyncMock(return_value=MagicMock(ok=True)),
        ) as write:
            await alerts_admin_write.resolve_service_alert(db, alert_id)
        kwargs = write.call_args.kwargs
        assert kwargs["table"] == "service_alerts"
        assert kwargs["operation"] == "update"
        assert set(kwargs["fields"]) == {"id", "resolved_at"}
        assert kwargs["fields"]["id"] == str(alert_id)

    @pytest.mark.asyncio
    async def test_gate_rejection_raises(self):
        row = MagicMock(resolved_at=None)
        db = self._db_returning(row)
        with patch.object(
            alerts_admin_write,
            "write_meta_async",
            new=AsyncMock(return_value=MagicMock(ok=False)),
        ):
            with pytest.raises(RuntimeError):
                await alerts_admin_write.resolve_service_alert(db, uuid4())
