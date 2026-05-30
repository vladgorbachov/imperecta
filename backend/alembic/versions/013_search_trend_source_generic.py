"""Drop marketplace-specific fact_search_trend source enum values."""

from __future__ import annotations

from alembic import op

revision = "013_search_trend_source_generic"
down_revision = "012_enable_rls_public_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE fact_search_trend
        SET source = 'custom'
        WHERE source IN ('kaspi_trends', 'allegro_trends');
        """
    )
    op.execute(
        "ALTER TABLE fact_search_trend DROP CONSTRAINT IF EXISTS ck_fact_search_trend_source;"
    )
    op.execute(
        """
        ALTER TABLE fact_search_trend
        ADD CONSTRAINT ck_fact_search_trend_source
        CHECK (source IN ('google_trends', 'amazon_trends', 'custom'));
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE fact_search_trend DROP CONSTRAINT IF EXISTS ck_fact_search_trend_source;"
    )
    op.execute(
        """
        ALTER TABLE fact_search_trend
        ADD CONSTRAINT ck_fact_search_trend_source
        CHECK (source IN (
            'google_trends', 'kaspi_trends', 'amazon_trends', 'allegro_trends', 'custom'
        ));
        """
    )
