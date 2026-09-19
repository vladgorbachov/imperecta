"""gate.exec_write_rows — set-based signed inserts for the pool tables.

Revision ID: 069_gate_exec_write_rows
Revises: 068_listing_shop_checked_index
Create Date: 2026-09-19

Enumeration wrote every dim_product / fact_listing row through
gate.exec_write: per row a plpgsql call that re-reads the signing secret
from vault, looks each column's type up in pg_attribute, builds an INSERT
with format() and EXECUTEs it. Measured in prod 2026-09-19: 5.7 ms per
dim_product row of which only 1.8 ms is the INSERT itself.

exec_write_rows keeps the security model exactly (every row still carries
its own HMAC over the same canonical bytes gate.exec_write verifies) and
changes only the mechanics: the secret is read once per batch, column
types are resolved once per column, and all rows go in through ONE
INSERT ... SELECT FROM jsonb_array_elements(). Rows must share one column
set (heterogeneous batches raise and the client falls back per record).
Restricted to the pool onboarding tables; the special-cased tables in
exec_write (fact_price and the market snapshots) keep their own path.
"""

from __future__ import annotations

from alembic import op

revision = "069_gate_exec_write_rows"
down_revision = "068_listing_shop_checked_index"
branch_labels = None
depends_on = None

_SEARCH_PATH = "SET search_path = pg_catalog, public, extensions, pg_temp"
_SIGNATURE = "gate.exec_write_rows(text, gate.row_payload[], text[])"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION gate.exec_write_rows(
            p_table text,
            p_rows gate.row_payload[],
            p_signatures text[]
        )
        RETURNS integer
        LANGUAGE plpgsql
        SECURITY DEFINER
        {_SEARCH_PATH}
        AS $fn$
        DECLARE
            secret_bytes bytea;
            tbl regclass;
            n integer;
            i integer;
            j integer;
            row_item gate.row_payload;
            entry gate.field_entry;
            expected text;
            canonical bytea;
            locator_keys text[];
            locator gate.field_entry[];
            first_keys text[] := ARRAY[]::text[];
            row_keys text[];
            payload jsonb := '[]'::jsonb;
            row_obj jsonb;
            col_names text[] := ARRAY[]::text[];
            col_exprs text[] := ARRAY[]::text[];
            col_type text;
            affected integer;
        BEGIN
            IF p_table NOT IN ('dim_product', 'fact_listing') THEN
                RAISE EXCEPTION 'unsupported_operation';
            END IF;
            IF NOT gate._operation_allowed(p_table, 'insert') THEN
                RAISE EXCEPTION 'unsupported_operation';
            END IF;
            tbl := to_regclass(format('public.%I', p_table));
            IF tbl IS NULL THEN
                RAISE EXCEPTION 'unsupported_operation';
            END IF;
            n := coalesce(array_length(p_rows, 1), 0);
            IF n = 0 THEN
                RETURN 0;
            END IF;
            IF coalesce(array_length(p_signatures, 1), 0) <> n THEN
                RAISE EXCEPTION 'invalid_signature';
            END IF;

            -- One vault read per batch instead of one per row.
            secret_bytes := convert_to(gate._signing_secret(), 'UTF8');
            locator_keys := gate._locator_keys(p_table);

            FOR i IN 1..n LOOP
                row_item := p_rows[i];
                -- The client signs (table, op, locator, fields) with the
                -- locator = the row's own locator columns, keys sorted —
                -- rebuilt here from the fields so the wire carries them once.
                locator := ARRAY[]::gate.field_entry[];
                FOREACH entry IN ARRAY row_item.fields LOOP
                    IF entry.key = ANY(locator_keys) THEN
                        locator := array_append(locator, entry);
                    END IF;
                END LOOP;
                canonical := gate._canonical_record(p_table, 'insert', locator, row_item.fields);
                expected := encode(extensions.hmac(canonical, secret_bytes, 'sha256'), 'hex');
                IF p_signatures[i] IS NULL
                   OR length(p_signatures[i]) <> length(expected)
                   OR p_signatures[i] <> expected THEN
                    RAISE EXCEPTION 'invalid_signature';
                END IF;

                row_keys := ARRAY[]::text[];
                row_obj := '{{}}'::jsonb;
                FOREACH entry IN ARRAY row_item.fields LOOP
                    row_keys := array_append(row_keys, entry.key);
                    IF entry.is_null THEN
                        row_obj := row_obj || jsonb_build_object(entry.key, NULL);
                    ELSE
                        row_obj := row_obj || jsonb_build_object(entry.key, entry.val);
                    END IF;
                END LOOP;
                IF i = 1 THEN
                    first_keys := row_keys;
                ELSIF row_keys <> first_keys THEN
                    RAISE EXCEPTION 'heterogeneous_rows';
                END IF;
                payload := payload || jsonb_build_array(row_obj);
            END LOOP;

            -- Column types resolved once per column, not once per cell.
            FOR j IN 1..array_length(first_keys, 1) LOOP
                SELECT format_type(a.atttypid, a.atttypmod)
                INTO col_type
                FROM pg_catalog.pg_attribute AS a
                WHERE a.attrelid = tbl
                  AND a.attname = first_keys[j]
                  AND a.attnum > 0
                  AND NOT a.attisdropped;
                IF col_type IS NULL THEN
                    RAISE EXCEPTION 'unsupported_column: %', first_keys[j];
                END IF;
                col_names := array_append(col_names, quote_ident(first_keys[j]));
                col_exprs := array_append(
                    col_exprs,
                    format('(r->>%L)::%s', first_keys[j], col_type)
                );
            END LOOP;

            EXECUTE format(
                'INSERT INTO %s (%s) SELECT %s FROM jsonb_array_elements($1) AS r',
                tbl,
                array_to_string(col_names, ', '),
                array_to_string(col_exprs, ', ')
            ) USING payload;
            GET DIAGNOSTICS affected = ROW_COUNT;
            RETURN affected;
        END;
        $fn$;
        """
    )
    op.execute(f"REVOKE EXECUTE ON FUNCTION {_SIGNATURE} FROM PUBLIC;")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_SIGNATURE} TO imperecta_app;")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION IF EXISTS {_SIGNATURE};")
