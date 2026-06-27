"""Seed wide-list dim_country rows (8) and TMT currency for Zone B.

Revision ID: 034_dim_country_wide_list_seed
Revises: 033_dim_country_world_zz
Create Date: 2026-06-27
"""

from alembic import op

revision = "034_dim_country_wide_list_seed"
down_revision = "033_dim_country_world_zz"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO dim_currency (
            currency_code, name, symbol, decimal_places, is_active
        )
        VALUES (
            'TMT', 'Turkmenistani Manat', 'm', 2, true
        )
        ON CONFLICT (currency_code) DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO dim_country (
            country_code, name, name_local, region, currency_code, vat_rate_std, is_active
        )
        VALUES (
            'TM', 'Turkmenistan', 'Türkmenistan', 'Central_Asia', 'TMT', NULL, true
        )
        ON CONFLICT (country_code) DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO dim_country (
            country_code, name, name_local, region, currency_code, vat_rate_std, is_active
        )
        VALUES (
            'AD', 'Andorra', 'Andorra', 'Other', 'EUR', NULL, true
        )
        ON CONFLICT (country_code) DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO dim_country (
            country_code, name, name_local, region, currency_code, vat_rate_std, is_active
        )
        VALUES (
            'CY', 'Cyprus', 'Κύπρος', 'EU', 'EUR', NULL, true
        )
        ON CONFLICT (country_code) DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO dim_country (
            country_code, name, name_local, region, currency_code, vat_rate_std, is_active
        )
        VALUES (
            'IS', 'Iceland', 'Ísland', 'EFTA', 'ISK', NULL, true
        )
        ON CONFLICT (country_code) DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO dim_country (
            country_code, name, name_local, region, currency_code, vat_rate_std, is_active
        )
        VALUES (
            'XK', 'Kosovo', 'Kosova', 'Balkans', 'EUR', NULL, true
        )
        ON CONFLICT (country_code) DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO dim_country (
            country_code, name, name_local, region, currency_code, vat_rate_std, is_active
        )
        VALUES (
            'LI', 'Liechtenstein', 'Liechtenstein', 'EFTA', 'CHF', NULL, true
        )
        ON CONFLICT (country_code) DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO dim_country (
            country_code, name, name_local, region, currency_code, vat_rate_std, is_active
        )
        VALUES (
            'LU', 'Luxembourg', 'Lëtzebuerg', 'EU', 'EUR', NULL, true
        )
        ON CONFLICT (country_code) DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO dim_country (
            country_code, name, name_local, region, currency_code, vat_rate_std, is_active
        )
        VALUES (
            'MT', 'Malta', 'Malta', 'EU', 'EUR', NULL, true
        )
        ON CONFLICT (country_code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM dim_country
        WHERE country_code IN ('TM', 'AD', 'CY', 'IS', 'XK', 'LI', 'LU', 'MT')
        """
    )
    op.execute("DELETE FROM dim_currency WHERE currency_code = 'TMT'")
