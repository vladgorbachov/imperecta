"""Seed dim_country sentinel ZZ (World / International).

Revision ID: 033_dim_country_world_zz
Revises: 032_service_alerts_and_alert_class
Create Date: 2026-06-25
"""

from alembic import op

revision = "033_dim_country_world_zz"
down_revision = "032_service_alerts_and_alert_class"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO dim_country (
            country_code, name, name_local, region, currency_code, vat_rate_std
        )
        VALUES (
            'ZZ', 'World', 'World', 'Other', 'EUR', NULL
        )
        ON CONFLICT (country_code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM dim_country WHERE country_code = 'ZZ'")
