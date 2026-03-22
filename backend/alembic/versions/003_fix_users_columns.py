"""Fix missing users columns and pg_trgm extension."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003_fix_users_columns"
down_revision = "002_v2_additions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure pg_trgm extension (may not be available during earlier migration run).
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))

    # Add missing users columns (safe on already-correct schemas).
    op.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS timezone VARCHAR(50) DEFAULT 'UTC'"))
    op.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS default_currency VARCHAR(3) DEFAULT 'EUR'"))
    op.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS telegram_username VARCHAR(100)"))
    op.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true"))
    op.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_ip INET"))
    op.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS login_count INTEGER DEFAULT 0"))


def downgrade() -> None:
    pass
