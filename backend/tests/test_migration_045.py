"""Migration 045 — grant imperecta_app INSERT on service_alerts."""

from __future__ import annotations

import ast
import re
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_045 = (
    BACKEND_ROOT / "alembic/versions/045_grant_app_insert_service_alerts.py"
)


def test_migration_045_py_compile() -> None:
    ast.parse(MIGRATION_045.read_text(encoding="utf-8"))


def test_migration_045_revision_chain() -> None:
    source = MIGRATION_045.read_text(encoding="utf-8")
    assert 'revision = "045_grant_app_insert_service_alerts"' in source
    assert 'down_revision = "044_widen_scrape_logs_status"' in source


def test_migration_045_grant_insert() -> None:
    source = MIGRATION_045.read_text(encoding="utf-8")
    assert "GRANT INSERT ON service_alerts TO imperecta_app" in source
    assert "REVOKE INSERT ON service_alerts FROM imperecta_app" in source
    assert "9.6" in source or "reject_data" in source


def test_migration_045_chain_head() -> None:
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

    assert revisions.get("045_grant_app_insert_service_alerts") == "044_widen_scrape_logs_status"
    children = [rev for rev, down in revisions.items() if down == "045_grant_app_insert_service_alerts"]
    assert children == [], f"045 is not head: children={children}"
