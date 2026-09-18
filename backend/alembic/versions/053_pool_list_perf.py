"""Search and sort indexes for /pool/products at 1.4M rows (P12).

Revision ID: 053_pool_list_perf
Revises: 052_stale_due_index
Create Date: 2026-09-18

Load rule (Imperecta_Architecture §1): 10k concurrent readers now, a
foundation that scales to 10M. The list endpoint's remaining table scans:

1. Search — `DimProduct.name ILIKE '%q%'` cannot use btree; a pg_trgm GIN
   index serves infix ILIKE directly. The extension lives in the
   `extensions` schema on Supabase; the operator class is schema-qualified
   because migrations run with search_path=public.
2. name_asc/name_desc keyset — btree (name, id) matches the keyset
   ordering (name, id) exactly.

recent/trending keyset rides 052's idx_listing_checked_active; price sorts
ride 051's idx_listing_active_priced. Plain in-transaction builds
(autocommit_block is broken under the async alembic env — see 051).
"""

from __future__ import annotations

from alembic import op

revision = "053_pool_list_perf"
down_revision = "052_stale_due_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL statement_timeout = '600s'")
    op.execute(
        """
        DO $do$
        DECLARE ext_schema text;
        BEGIN
            SELECT n.nspname INTO ext_schema
            FROM pg_extension e JOIN pg_namespace n ON n.oid = e.extnamespace
            WHERE e.extname = 'pg_trgm';
            IF ext_schema IS NULL THEN
                CREATE EXTENSION pg_trgm WITH SCHEMA extensions;
                ext_schema := 'extensions';
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_class WHERE relname = 'idx_dim_product_name_trgm'
            ) THEN
                EXECUTE format(
                    'CREATE INDEX idx_dim_product_name_trgm '
                    'ON dim_product USING gin (name %I.gin_trgm_ops)',
                    ext_schema
                );
            END IF;
        END
        $do$;
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_dim_product_name_id "
        "ON dim_product (name, id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_dim_product_name_id")
    op.execute("DROP INDEX IF EXISTS idx_dim_product_name_trgm")
