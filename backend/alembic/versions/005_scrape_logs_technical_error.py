"""Add technical_error to scrape_logs.status CHECK."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "005_scrape_logs_technical_error"
down_revision = "004_fix_real_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TABLE scrape_logs DROP CONSTRAINT IF EXISTS ck_scrape_logs_status"))
    op.execute(
        sa.text(
            "ALTER TABLE scrape_logs ADD CONSTRAINT ck_scrape_logs_status CHECK (status IN ("
            "'success','error','timeout','blocked','captcha',"
            "'not_found','price_not_found','parse_error','missing_critical_data',"
            "'technical_error'"
            "))"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE scrape_logs DROP CONSTRAINT IF EXISTS ck_scrape_logs_status"))
    op.execute(
        sa.text(
            "ALTER TABLE scrape_logs ADD CONSTRAINT ck_scrape_logs_status CHECK (status IN ("
            "'success','error','timeout','blocked','captcha',"
            "'not_found','price_not_found','parse_error','missing_critical_data'"
            "))"
        )
    )
