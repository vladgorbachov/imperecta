"""Product type + universal-language (EN) fields on dim_product (P13).

Revision ID: 054_product_type_en_layer
Revises: 053_pool_list_perf
Create Date: 2026-09-18

The UI's Type column and EN rendering layer read three nullable columns:
product_type (source-language, e.g. breadcrumb leaf / classifier),
product_type_en and title_en (machine-translated at enrichment time —
never per request). dim_category already carries name_en, so category_en
needs no schema change. All nullable — honest null until the enrichment
pipeline fills them; the gate's product_enrich door allowlists the new
columns for that future write path.
"""

from __future__ import annotations

from alembic import op

revision = "054_product_type_en_layer"
down_revision = "053_pool_list_perf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE dim_product ADD COLUMN IF NOT EXISTS product_type varchar(200)")
    op.execute(
        "ALTER TABLE dim_product ADD COLUMN IF NOT EXISTS product_type_en varchar(200)"
    )
    op.execute("ALTER TABLE dim_product ADD COLUMN IF NOT EXISTS title_en varchar(500)")


def downgrade() -> None:
    op.execute("ALTER TABLE dim_product DROP COLUMN IF EXISTS title_en")
    op.execute("ALTER TABLE dim_product DROP COLUMN IF EXISTS product_type_en")
    op.execute("ALTER TABLE dim_product DROP COLUMN IF EXISTS product_type")
