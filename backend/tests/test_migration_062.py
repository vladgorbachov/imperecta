"""Migration 062 — alerts in_app channel + channels jsonb (source invariants)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_062 = BACKEND_ROOT / "alembic/versions/062_alert_in_app_channels.py"


def test_migration_062_py_compile() -> None:
    ast.parse(MIGRATION_062.read_text(encoding="utf-8"))


def test_migration_062_revision_chain() -> None:
    source = MIGRATION_062.read_text(encoding="utf-8")
    assert 'revision = "062_alert_in_app_channels"' in source
    assert 'down_revision = "061_product_match_columns"' in source


def test_migration_062_extends_check_and_adds_channels() -> None:
    source = MIGRATION_062.read_text(encoding="utf-8")
    assert "'in_app'" in source
    assert "ADD COLUMN IF NOT EXISTS channels jsonb" in source
    assert "jsonb_typeof(channels) = 'array'" in source
    assert "jsonb_array_length(channels) >= 1" in source
    # Backfill of pre-P15 rows: channels = [channel].
    assert "to_jsonb(ARRAY[channel])" in source
    # This env cannot run CONCURRENTLY/autocommit DDL (async alembic bridge).
    assert "autocommit_block" not in source
    assert "CONCURRENTLY" not in source


def test_model_matches_migration() -> None:
    from app.models.app_tables import Alert

    assert "channels" in Alert.__table__.columns
    checks = {
        c.name: str(c.sqltext)
        for c in Alert.__table_args__
        if hasattr(c, "sqltext")
    }
    assert "in_app" in checks["ck_alerts_channel"]
    assert "jsonb_typeof" in checks["ck_alerts_channels"]


def test_alembic_chain_includes_062() -> None:
    versions_dir = BACKEND_ROOT / "alembic" / "versions"
    revisions: dict[str, str | None] = {}
    for path in versions_dir.glob("*.py"):
        if path.name.startswith("__"):
            continue
        source = path.read_text(encoding="utf-8")
        rev_match = re.search(r'^revision\s*=\s*"([^"]+)"', source, re.MULTILINE)
        down_match = re.search(r'^down_revision\s*=\s*"([^"]+)"', source, re.MULTILINE)
        if rev_match is None:
            continue
        revisions[rev_match.group(1)] = down_match.group(1) if down_match else None
    assert revisions["062_alert_in_app_channels"] == "061_product_match_columns"
