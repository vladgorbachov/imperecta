"""Widen scrape_logs.status to VARCHAR(50) (DDL-eviction E3a).

Revision ID: 044_widen_scrape_logs_status
Revises: 043_pgcron_refresh_mviews
Create Date: 2026-06-29

Purpose: fix real schema drift — production scrape_logs.status remained
VARCHAR(20) while the ORM model uses String(50) and canonical terminal status
``missing_critical_data`` is 21 characters. A runtime ALTER repair in
scraper/service.py masked the drift; that repair is removed in E3a.

Metadata-only widening (no table rewrite). Migration 006 attempted the same
widening with conditional logic; this migration applies the widen unconditionally
for databases still at VARCHAR(20).

No app DATABASE_URL switch, no DML revoke, no persist rewire.
"""

from __future__ import annotations

from alembic import op

revision = "044_widen_scrape_logs_status"
down_revision = "043_pgcron_refresh_mviews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE scrape_logs ALTER COLUMN status TYPE VARCHAR(50)")


def downgrade() -> None:
    # Formal reverse; fails if any stored status exceeds 20 characters.
    op.execute("ALTER TABLE scrape_logs ALTER COLUMN status TYPE VARCHAR(20)")
