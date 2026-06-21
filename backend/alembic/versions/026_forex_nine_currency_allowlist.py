"""Seed JPY and purge non-allowlisted forex fact rows.

Revision ID: 026_forex_nine_currency_allowlist
Revises: 025_supabase_security_hardening
Create Date: 2026-06-20
"""

from alembic import op

revision = "026_forex_nine_currency_allowlist"
down_revision = "025_supabase_security_hardening"
branch_labels = None
depends_on = None

_FOREX_NINE = (
    "'USD','EUR','GBP','JPY','CHF','MDL','RON','PLN','TRY'"
)


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO dim_currency (
            currency_code, name, symbol, decimal_places, is_active
        )
        VALUES ('JPY', 'Japanese Yen', '¥', 0, true)
        ON CONFLICT (currency_code) DO NOTHING
        """
    )
    op.execute(
        f"DELETE FROM fact_currency_rate WHERE currency_code NOT IN ({_FOREX_NINE})"
    )


def downgrade() -> None:
    op.execute("DELETE FROM dim_currency WHERE currency_code = 'JPY'")
