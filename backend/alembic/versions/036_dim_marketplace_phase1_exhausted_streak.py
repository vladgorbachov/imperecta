"""dim_marketplace phase1_exhausted_streak for discovery defence-in-depth.

Revision ID: 036_dim_marketplace_phase1_exhausted_streak
Revises: 035_dim_marketplace_sitemap_bad_harvest_streak
Create Date: 2026-06-17
"""

from alembic import op

from app.modules.persist.maintenance_audit import record_maintenance_audit

revision = "036_dim_marketplace_phase1_exhausted_streak"
down_revision = "035_dim_marketplace_sitemap_bad_harvest_streak"
branch_labels = None
depends_on = None


def _audit_ddl(target: str, detail: str) -> None:
    """Record DDL through the LOGS door (api_logs maintenance audit mark)."""
    record_maintenance_audit(
        op="ALTER",
        target=target,
        status="success",
        detail=detail,
    )


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE dim_marketplace
        ADD COLUMN phase1_exhausted_streak integer NOT NULL DEFAULT 0
        """
    )
    _audit_ddl(
        "dim_marketplace.phase1_exhausted_streak",
        "ADD COLUMN phase1_exhausted_streak integer NOT NULL DEFAULT 0",
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE dim_marketplace
        DROP COLUMN IF EXISTS phase1_exhausted_streak
        """
    )
    _audit_ddl(
        "dim_marketplace.phase1_exhausted_streak",
        "DROP COLUMN phase1_exhausted_streak",
    )
