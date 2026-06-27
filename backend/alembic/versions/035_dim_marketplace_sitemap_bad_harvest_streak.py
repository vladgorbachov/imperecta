"""dim_marketplace sitemap_bad_harvest_streak for discovery defence-in-depth.

Revision ID: 035_dim_marketplace_sitemap_bad_harvest_streak
Revises: 034_dim_country_wide_list_seed
Create Date: 2026-06-17
"""

from alembic import op

from app.modules.persist.maintenance_audit import record_maintenance_audit

revision = "035_dim_marketplace_sitemap_bad_harvest_streak"
down_revision = "034_dim_country_wide_list_seed"
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
        ADD COLUMN sitemap_bad_harvest_streak integer NOT NULL DEFAULT 0
        """
    )
    _audit_ddl(
        "dim_marketplace.sitemap_bad_harvest_streak",
        "ADD COLUMN sitemap_bad_harvest_streak integer NOT NULL DEFAULT 0",
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE dim_marketplace
        DROP COLUMN IF EXISTS sitemap_bad_harvest_streak
        """
    )
    _audit_ddl(
        "dim_marketplace.sitemap_bad_harvest_streak",
        "DROP COLUMN sitemap_bad_harvest_streak",
    )
