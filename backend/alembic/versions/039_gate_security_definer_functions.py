"""SECURITY DEFINER gate functions — HMAC verify + typed CUD (Level 2 seam 9.2).

Revision ID: 039_gate_security_definer_functions
Revises: 038_create_imperecta_app_role
Create Date: 2026-06-28

Purpose: Variant B wire — persist sends pre-canonical ordered (key, is_null, val)
arrays; plpgsql reproduces B2 bytes, verifies HMAC-SHA256 (pgcrypto + vault secret
``data_firewall_signing_secret``), then executes CUD mirroring persist/writer.py.

IDLE until seam 9.3 GRANT EXECUTE to imperecta_app and seam 9.4 persist rewire.
EXECUTE revoked from PUBLIC on every function. Password/secret never in repo.

Prerequisites (Supabase): extensions ``pgcrypto`` (schema ``extensions``),
``supabase_vault`` (schema ``vault``); operator stores signing secret in vault
under name ``data_firewall_signing_secret`` (read via
``vault.decrypted_secrets.decrypted_secret``).
"""

from __future__ import annotations

from alembic import op

revision = "039_gate_security_definer_functions"
down_revision = "038_create_imperecta_app_role"
branch_labels = None
depends_on = None

_SEARCH_PATH = "SET search_path = pg_catalog, public, extensions, pg_temp"


def _create(sql: str) -> None:
    op.execute(sql)


def _revoke(signature: str) -> None:
    op.execute(f"REVOKE EXECUTE ON {signature} FROM PUBLIC;")


def upgrade() -> None:
    _create("CREATE SCHEMA IF NOT EXISTS gate;")

    _create(
        """
        CREATE TYPE gate.field_entry AS (
            key text,
            is_null boolean,
            val text
        );
        """
    )

    _create(
        """
        CREATE TYPE gate.row_payload AS (
            fields gate.field_entry[]
        );
        """
    )

    _create(
        f"""
        CREATE OR REPLACE FUNCTION gate._lp_string(p_value text)
        RETURNS bytea
        LANGUAGE plpgsql
        IMMUTABLE
        STRICT
        {_SEARCH_PATH}
        AS $fn$
        BEGIN
            RETURN convert_to(octet_length(p_value)::text || ':' || p_value, 'UTF8');
        END;
        $fn$;
        """
    )
    _revoke("FUNCTION gate._lp_string(text)")

    _create(
        f"""
        CREATE OR REPLACE FUNCTION gate._val_enc(p_is_null boolean, p_val text)
        RETURNS bytea
        LANGUAGE plpgsql
        IMMUTABLE
        {_SEARCH_PATH}
        AS $fn$
        BEGIN
            IF p_is_null THEN
                RETURN convert_to('N', 'UTF8');
            END IF;
            RETURN convert_to('S', 'UTF8') || gate._lp_string(p_val);
        END;
        $fn$;
        """
    )
    _revoke("FUNCTION gate._val_enc(boolean, text)")

    _create(
        f"""
        CREATE OR REPLACE FUNCTION gate._dict_enc(p_entries gate.field_entry[])
        RETURNS bytea
        LANGUAGE plpgsql
        IMMUTABLE
        {_SEARCH_PATH}
        AS $fn$
        DECLARE
            result bytea := convert_to('D' || coalesce(array_length(p_entries, 1), 0)::text, 'UTF8');
            entry gate.field_entry;
        BEGIN
            IF p_entries IS NULL THEN
                RETURN result;
            END IF;
            FOREACH entry IN ARRAY p_entries LOOP
                result := result
                    || gate._lp_string(entry.key)
                    || gate._val_enc(entry.is_null, entry.val);
            END LOOP;
            RETURN result;
        END;
        $fn$;
        """
    )
    _revoke("FUNCTION gate._dict_enc(gate.field_entry[])")

    _create(
        f"""
        CREATE OR REPLACE FUNCTION gate._canonical_record(
            p_table text,
            p_operation text,
            p_locator gate.field_entry[],
            p_fields gate.field_entry[]
        )
        RETURNS bytea
        LANGUAGE plpgsql
        IMMUTABLE
        {_SEARCH_PATH}
        AS $fn$
        BEGIN
            RETURN convert_to('T', 'UTF8')
                || gate._lp_string(p_table)
                || convert_to('O', 'UTF8')
                || gate._lp_string(p_operation)
                || convert_to('L', 'UTF8')
                || gate._dict_enc(p_locator)
                || convert_to('F', 'UTF8')
                || gate._dict_enc(p_fields);
        END;
        $fn$;
        """
    )
    _revoke(
        "FUNCTION gate._canonical_record(text, text, gate.field_entry[], gate.field_entry[])"
    )

    _create(
        f"""
        CREATE OR REPLACE FUNCTION gate._canonical_batch(
            p_table text,
            p_operation text,
            p_locator gate.field_entry[],
            p_rows gate.row_payload[]
        )
        RETURNS bytea
        LANGUAGE plpgsql
        IMMUTABLE
        {_SEARCH_PATH}
        AS $fn$
        DECLARE
            result bytea;
            row_item gate.row_payload;
        BEGIN
            result := convert_to('T', 'UTF8')
                || gate._lp_string(p_table)
                || convert_to('O', 'UTF8')
                || gate._lp_string(p_operation)
                || convert_to('L', 'UTF8')
                || gate._dict_enc(p_locator)
                || convert_to('R', 'UTF8')
                || convert_to(coalesce(array_length(p_rows, 1), 0)::text, 'UTF8');
            IF p_rows IS NOT NULL THEN
                FOREACH row_item IN ARRAY p_rows LOOP
                    result := result || gate._dict_enc(row_item.fields);
                END LOOP;
            END IF;
            RETURN result;
        END;
        $fn$;
        """
    )
    _revoke(
        "FUNCTION gate._canonical_batch(text, text, gate.field_entry[], gate.row_payload[])"
    )

    _create(
        f"""
        CREATE OR REPLACE FUNCTION gate._signing_secret()
        RETURNS text
        LANGUAGE plpgsql
        STABLE
        SECURITY DEFINER
        {_SEARCH_PATH}
        AS $fn$
        DECLARE
            secret text;
        BEGIN
            SELECT ds.decrypted_secret
            INTO secret
            FROM vault.decrypted_secrets AS ds
            WHERE ds.name = 'data_firewall_signing_secret'
            LIMIT 1;
            IF secret IS NULL OR btrim(secret) = '' THEN
                RAISE EXCEPTION 'signing_unavailable';
            END IF;
            RETURN secret;
        END;
        $fn$;
        """
    )
    _revoke("FUNCTION gate._signing_secret()")

    _create(
        f"""
        CREATE OR REPLACE FUNCTION gate._hmac_hex(p_canonical bytea)
        RETURNS text
        LANGUAGE plpgsql
        STABLE
        SECURITY DEFINER
        {_SEARCH_PATH}
        AS $fn$
        DECLARE
            secret text;
        BEGIN
            secret := gate._signing_secret();
            RETURN encode(
                extensions.hmac(p_canonical, convert_to(secret, 'UTF8'), 'sha256'),
                'hex'
            );
        END;
        $fn$;
        """
    )
    _revoke("FUNCTION gate._hmac_hex(bytea)")

    _create(
        f"""
        CREATE OR REPLACE FUNCTION gate._assert_signature(
            p_canonical bytea,
            p_signature text
        )
        RETURNS void
        LANGUAGE plpgsql
        STABLE
        SECURITY DEFINER
        {_SEARCH_PATH}
        AS $fn$
        DECLARE
            expected text;
        BEGIN
            expected := gate._hmac_hex(p_canonical);
            IF p_signature IS NULL OR length(p_signature) <> length(expected) OR p_signature <> expected THEN
                RAISE EXCEPTION 'invalid_signature';
            END IF;
        END;
        $fn$;
        """
    )
    _revoke("FUNCTION gate._assert_signature(bytea, text)")

    _create(
        f"""
        CREATE OR REPLACE FUNCTION gate._entry_text(
            p_entries gate.field_entry[],
            p_key text
        )
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        {_SEARCH_PATH}
        AS $fn$
            SELECT e.val
            FROM unnest(COALESCE($1, ARRAY[]::gate.field_entry[])) AS e
            WHERE e.key = $2
            LIMIT 1;
        $fn$;
        """
    )
    _revoke("FUNCTION gate._entry_text(gate.field_entry[], text)")

    _create(
        f"""
        CREATE OR REPLACE FUNCTION gate._entry_is_null(
            p_entries gate.field_entry[],
            p_key text
        )
        RETURNS boolean
        LANGUAGE sql
        IMMUTABLE
        {_SEARCH_PATH}
        AS $fn$
            SELECT COALESCE(
                (
                    SELECT e.is_null
                    FROM unnest(COALESCE($1, ARRAY[]::gate.field_entry[])) AS e
                    WHERE e.key = $2
                    LIMIT 1
                ),
                TRUE
            );
        $fn$;
        """
    )
    _revoke("FUNCTION gate._entry_is_null(gate.field_entry[], text)")

    _create(
        f"""
        CREATE OR REPLACE FUNCTION gate._typed_literal(
            p_table regclass,
            p_column text,
            p_is_null boolean,
            p_val text
        )
        RETURNS text
        LANGUAGE plpgsql
        STABLE
        {_SEARCH_PATH}
        AS $fn$
        DECLARE
            col_type text;
        BEGIN
            IF p_is_null THEN
                RETURN 'NULL';
            END IF;
            SELECT format_type(a.atttypid, a.atttypmod)
            INTO col_type
            FROM pg_catalog.pg_attribute AS a
            WHERE a.attrelid = p_table
              AND a.attname = p_column
              AND a.attnum > 0
              AND NOT a.attisdropped;
            IF col_type IS NULL THEN
                RAISE EXCEPTION 'unsupported_column: %', p_column;
            END IF;
            RETURN format('%L::%s', p_val, col_type);
        END;
        $fn$;
        """
    )
    _revoke("FUNCTION gate._typed_literal(regclass, text, boolean, text)")

    _create(
        f"""
        CREATE OR REPLACE FUNCTION gate._insert_from_entries(
            p_table regclass,
            p_entries gate.field_entry[]
        )
        RETURNS integer
        LANGUAGE plpgsql
        SECURITY DEFINER
        {_SEARCH_PATH}
        AS $fn$
        DECLARE
            col_names text[] := ARRAY[]::text[];
            val_exprs text[] := ARRAY[]::text[];
            entry gate.field_entry;
            sql text;
            affected integer;
        BEGIN
            IF p_entries IS NULL OR array_length(p_entries, 1) IS NULL THEN
                RETURN 0;
            END IF;
            FOREACH entry IN ARRAY p_entries LOOP
                col_names := array_append(col_names, quote_ident(entry.key));
                val_exprs := array_append(
                    val_exprs,
                    gate._typed_literal(p_table, entry.key, entry.is_null, entry.val)
                );
            END LOOP;
            sql := format(
                'INSERT INTO %s (%s) VALUES (%s)',
                p_table,
                array_to_string(col_names, ', '),
                array_to_string(val_exprs, ', ')
            );
            EXECUTE sql;
            GET DIAGNOSTICS affected = ROW_COUNT;
            RETURN affected;
        END;
        $fn$;
        """
    )
    _revoke("FUNCTION gate._insert_from_entries(regclass, gate.field_entry[])")

    _create(
        f"""
        CREATE OR REPLACE FUNCTION gate._update_from_entries(
            p_table regclass,
            p_locator_keys text[],
            p_locator gate.field_entry[],
            p_fields gate.field_entry[]
        )
        RETURNS integer
        LANGUAGE plpgsql
        SECURITY DEFINER
        {_SEARCH_PATH}
        AS $fn$
        DECLARE
            set_pairs text[] := ARRAY[]::text[];
            where_pairs text[] := ARRAY[]::text[];
            locator_key text;
            entry gate.field_entry;
            sql text;
            affected integer;
        BEGIN
            IF p_fields IS NOT NULL THEN
                FOREACH entry IN ARRAY p_fields LOOP
                    IF entry.key = ANY (p_locator_keys) THEN
                        CONTINUE;
                    END IF;
                    set_pairs := array_append(
                        set_pairs,
                        format(
                            '%I = %s',
                            entry.key,
                            gate._typed_literal(p_table, entry.key, entry.is_null, entry.val)
                        )
                    );
                END LOOP;
            END IF;
            IF coalesce(array_length(set_pairs, 1), 0) = 0 THEN
                RETURN 0;
            END IF;
            FOREACH locator_key IN ARRAY p_locator_keys LOOP
                where_pairs := array_append(
                    where_pairs,
                    format(
                        '%I = %s',
                        locator_key,
                        gate._typed_literal(
                            p_table,
                            locator_key,
                            gate._entry_is_null(p_locator, locator_key),
                            gate._entry_text(p_locator, locator_key)
                        )
                    )
                );
            END LOOP;
            sql := format(
                'UPDATE %s SET %s WHERE %s',
                p_table,
                array_to_string(set_pairs, ', '),
                array_to_string(where_pairs, ' AND ')
            );
            EXECUTE sql;
            GET DIAGNOSTICS affected = ROW_COUNT;
            RETURN affected;
        END;
        $fn$;
        """
    )
    _revoke(
        "FUNCTION gate._update_from_entries(regclass, text[], gate.field_entry[], gate.field_entry[])"
    )

    _create(
        f"""
        CREATE OR REPLACE FUNCTION gate._delete_from_locator(
            p_table regclass,
            p_locator_keys text[],
            p_locator gate.field_entry[]
        )
        RETURNS integer
        LANGUAGE plpgsql
        SECURITY DEFINER
        {_SEARCH_PATH}
        AS $fn$
        DECLARE
            where_pairs text[] := ARRAY[]::text[];
            locator_key text;
            sql text;
            affected integer;
        BEGIN
            FOREACH locator_key IN ARRAY p_locator_keys LOOP
                where_pairs := array_append(
                    where_pairs,
                    format(
                        '%I = %s',
                        locator_key,
                        gate._typed_literal(
                            p_table,
                            locator_key,
                            gate._entry_is_null(p_locator, locator_key),
                            gate._entry_text(p_locator, locator_key)
                        )
                    )
                );
            END LOOP;
            IF coalesce(array_length(where_pairs, 1), 0) = 0 THEN
                RAISE EXCEPTION 'unsupported_operation';
            END IF;
            sql := format('DELETE FROM %s WHERE %s', p_table, array_to_string(where_pairs, ' AND '));
            EXECUTE sql;
            GET DIAGNOSTICS affected = ROW_COUNT;
            RETURN affected;
        END;
        $fn$;
        """
    )
    _revoke("FUNCTION gate._delete_from_locator(regclass, text[], gate.field_entry[])")

    _create(
        f"""
        CREATE OR REPLACE FUNCTION gate._retention_delete(
            p_table regclass,
            p_fields gate.field_entry[]
        )
        RETURNS integer
        LANGUAGE plpgsql
        SECURITY DEFINER
        {_SEARCH_PATH}
        AS $fn$
        DECLARE
            cutoff_col text;
            cutoff_ts timestamptz;
            sql text;
            affected integer;
        BEGIN
            cutoff_col := gate._entry_text(p_fields, 'cutoff_column');
            IF gate._entry_is_null(p_fields, 'cutoff') THEN
                RAISE EXCEPTION 'unsupported_operation';
            END IF;
            cutoff_ts := gate._entry_text(p_fields, 'cutoff')::timestamptz;
            sql := format('DELETE FROM %s WHERE %I < %L', p_table, cutoff_col, cutoff_ts);
            EXECUTE sql;
            GET DIAGNOSTICS affected = ROW_COUNT;
            RETURN affected;
        END;
        $fn$;
        """
    )
    _revoke("FUNCTION gate._retention_delete(regclass, gate.field_entry[])")

    _create(
        f"""
        CREATE OR REPLACE FUNCTION gate._insert_dim_date(
            p_fields gate.field_entry[]
        )
        RETURNS integer
        LANGUAGE plpgsql
        SECURITY DEFINER
        {_SEARCH_PATH}
        AS $fn$
        DECLARE
            col_names text[] := ARRAY[]::text[];
            val_exprs text[] := ARRAY[]::text[];
            entry gate.field_entry;
            sql text;
            affected integer;
            tbl constant regclass := 'public.dim_date'::regclass;
        BEGIN
            IF p_fields IS NULL OR array_length(p_fields, 1) IS NULL THEN
                RETURN 0;
            END IF;
            FOREACH entry IN ARRAY p_fields LOOP
                col_names := array_append(col_names, quote_ident(entry.key));
                val_exprs := array_append(
                    val_exprs,
                    gate._typed_literal(tbl, entry.key, entry.is_null, entry.val)
                );
            END LOOP;
            sql := format(
                'INSERT INTO dim_date (%s) VALUES (%s) ON CONFLICT (date_id) DO NOTHING',
                array_to_string(col_names, ', '),
                array_to_string(val_exprs, ', ')
            );
            EXECUTE sql;
            GET DIAGNOSTICS affected = ROW_COUNT;
            RETURN affected;
        END;
        $fn$;
        """
    )
    _revoke("FUNCTION gate._insert_dim_date(gate.field_entry[])")

    _create(
        f"""
        CREATE OR REPLACE FUNCTION gate._operation_allowed(
            p_table text,
            p_operation text
        )
        RETURNS boolean
        LANGUAGE plpgsql
        IMMUTABLE
        {_SEARCH_PATH}
        AS $fn$
        BEGIN
            CASE p_table
                WHEN 'dim_date' THEN RETURN p_operation = 'insert';
                WHEN 'dim_product' THEN RETURN p_operation IN ('insert', 'update', 'delete');
                WHEN 'dim_marketplace' THEN RETURN p_operation IN ('insert', 'update', 'delete');
                WHEN 'scrape_jobs' THEN RETURN p_operation IN ('insert', 'update', 'delete');
                WHEN 'fact_listing' THEN RETURN p_operation IN ('insert', 'update', 'delete');
                WHEN 'fact_price' THEN RETURN p_operation IN ('insert', 'delete');
                WHEN 'fact_currency_rate' THEN RETURN p_operation IN ('insert', 'delete');
                WHEN 'fact_crypto_price' THEN RETURN p_operation IN ('insert', 'delete');
                WHEN 'fact_commodity_price' THEN RETURN p_operation IN ('insert', 'delete');
                WHEN 'scrape_logs' THEN RETURN p_operation IN ('insert', 'retention_delete');
                WHEN 'api_logs' THEN RETURN p_operation IN ('insert', 'retention_delete');
                WHEN 'service_alerts' THEN RETURN p_operation IN ('insert', 'retention_delete');
                WHEN 'reject_data' THEN RETURN p_operation = 'retention_delete';
                WHEN 'users' THEN RETURN p_operation IN ('insert', 'update', 'delete');
                WHEN 'ai_chat_sessions' THEN RETURN p_operation = 'insert';
                WHEN 'ai_chat_messages' THEN RETURN p_operation = 'insert';
                ELSE RETURN FALSE;
            END CASE;
        END;
        $fn$;
        """
    )
    _revoke("FUNCTION gate._operation_allowed(text, text)")

    _create(
        f"""
        CREATE OR REPLACE FUNCTION gate._locator_keys(p_table text)
        RETURNS text[]
        LANGUAGE plpgsql
        IMMUTABLE
        {_SEARCH_PATH}
        AS $fn$
        BEGIN
            CASE p_table
                WHEN 'dim_date' THEN RETURN ARRAY['date_id'];
                WHEN 'fact_price' THEN RETURN ARRAY['listing_id', 'date_id'];
                WHEN 'fact_listing' THEN RETURN ARRAY['url_hash'];
                WHEN 'dim_product' THEN RETURN ARRAY['id'];
                WHEN 'dim_marketplace' THEN RETURN ARRAY['id'];
                WHEN 'scrape_jobs' THEN RETURN ARRAY['id'];
                WHEN 'fact_currency_rate' THEN RETURN ARRAY['date_id', 'currency_code', 'source'];
                WHEN 'fact_crypto_price' THEN RETURN ARRAY['date_id', 'symbol', 'source'];
                WHEN 'fact_commodity_price' THEN RETURN ARRAY['date_id', 'symbol', 'source'];
                WHEN 'service_alerts' THEN RETURN ARRAY['id'];
                WHEN 'users' THEN RETURN ARRAY['id'];
                WHEN 'ai_chat_sessions' THEN RETURN ARRAY['id'];
                WHEN 'ai_chat_messages' THEN RETURN ARRAY['id'];
                WHEN 'scrape_logs' THEN RETURN ARRAY[]::text[];
                WHEN 'api_logs' THEN RETURN ARRAY[]::text[];
                WHEN 'reject_data' THEN RETURN ARRAY[]::text[];
                ELSE RETURN NULL;
            END CASE;
        END;
        $fn$;
        """
    )
    _revoke("FUNCTION gate._locator_keys(text)")

    _create(
        f"""
        CREATE OR REPLACE FUNCTION gate.exec_write(
            p_table text,
            p_operation text,
            p_locator gate.field_entry[],
            p_fields gate.field_entry[],
            p_signature text
        )
        RETURNS integer
        LANGUAGE plpgsql
        SECURITY DEFINER
        {_SEARCH_PATH}
        AS $fn$
        DECLARE
            canonical bytea;
            locator_keys text[];
            tbl regclass;
        BEGIN
            canonical := gate._canonical_record(p_table, p_operation, p_locator, p_fields);
            PERFORM gate._assert_signature(canonical, p_signature);

            IF NOT gate._operation_allowed(p_table, p_operation) THEN
                RAISE EXCEPTION 'unsupported_operation';
            END IF;

            locator_keys := gate._locator_keys(p_table);
            IF locator_keys IS NULL THEN
                RAISE EXCEPTION 'unsupported_operation';
            END IF;

            tbl := to_regclass(format('public.%I', p_table));
            IF tbl IS NULL THEN
                RAISE EXCEPTION 'unsupported_operation';
            END IF;

            IF p_operation = 'retention_delete' THEN
                RETURN gate._retention_delete(tbl, p_fields);
            END IF;

            IF p_operation = 'update' THEN
                RETURN gate._update_from_entries(tbl, locator_keys, p_locator, p_fields);
            END IF;

            IF p_operation = 'delete' THEN
                RETURN gate._delete_from_locator(tbl, locator_keys, p_locator);
            END IF;

            IF p_operation <> 'insert' THEN
                RAISE EXCEPTION 'unsupported_operation';
            END IF;

            IF p_table = 'fact_price' THEN
                EXECUTE format(
                    'DELETE FROM fact_price WHERE listing_id = %s AND date_id = %s',
                    gate._typed_literal(tbl, 'listing_id', gate._entry_is_null(p_fields, 'listing_id'), gate._entry_text(p_fields, 'listing_id')),
                    gate._typed_literal(tbl, 'date_id', gate._entry_is_null(p_fields, 'date_id'), gate._entry_text(p_fields, 'date_id'))
                );
                RETURN gate._insert_from_entries(tbl, p_fields);
            END IF;

            IF p_table = 'dim_date' THEN
                RETURN gate._insert_dim_date(p_fields);
            END IF;

            IF p_table = 'fact_currency_rate' THEN
                EXECUTE format(
                    'DELETE FROM fact_currency_rate WHERE date_id = %s AND currency_code = %s AND source = %s',
                    gate._typed_literal(tbl, 'date_id', gate._entry_is_null(p_fields, 'date_id'), gate._entry_text(p_fields, 'date_id')),
                    gate._typed_literal(tbl, 'currency_code', gate._entry_is_null(p_fields, 'currency_code'), gate._entry_text(p_fields, 'currency_code')),
                    gate._typed_literal(tbl, 'source', gate._entry_is_null(p_fields, 'source'), gate._entry_text(p_fields, 'source'))
                );
                RETURN gate._insert_from_entries(tbl, p_fields);
            END IF;

            IF p_table = 'fact_crypto_price' THEN
                EXECUTE format(
                    'DELETE FROM fact_crypto_price WHERE date_id = %s AND symbol = %s AND source = %s',
                    gate._typed_literal(tbl, 'date_id', gate._entry_is_null(p_fields, 'date_id'), gate._entry_text(p_fields, 'date_id')),
                    gate._typed_literal(tbl, 'symbol', gate._entry_is_null(p_fields, 'symbol'), gate._entry_text(p_fields, 'symbol')),
                    gate._typed_literal(tbl, 'source', gate._entry_is_null(p_fields, 'source'), gate._entry_text(p_fields, 'source'))
                );
                RETURN gate._insert_from_entries(tbl, p_fields);
            END IF;

            IF p_table = 'fact_commodity_price' THEN
                EXECUTE format(
                    'DELETE FROM fact_commodity_price WHERE date_id = %s AND symbol = %s AND source = %s',
                    gate._typed_literal(tbl, 'date_id', gate._entry_is_null(p_fields, 'date_id'), gate._entry_text(p_fields, 'date_id')),
                    gate._typed_literal(tbl, 'symbol', gate._entry_is_null(p_fields, 'symbol'), gate._entry_text(p_fields, 'symbol')),
                    gate._typed_literal(tbl, 'source', gate._entry_is_null(p_fields, 'source'), gate._entry_text(p_fields, 'source'))
                );
                RETURN gate._insert_from_entries(tbl, p_fields);
            END IF;

            RETURN gate._insert_from_entries(tbl, p_fields);
        END;
        $fn$;
        """
    )
    _revoke(
        "FUNCTION gate.exec_write(text, text, gate.field_entry[], gate.field_entry[], text)"
    )

    _create(
        f"""
        CREATE OR REPLACE FUNCTION gate.exec_write_batch(
            p_table text,
            p_operation text,
            p_locator gate.field_entry[],
            p_rows gate.row_payload[],
            p_signature text
        )
        RETURNS integer
        LANGUAGE plpgsql
        SECURITY DEFINER
        {_SEARCH_PATH}
        AS $fn$
        DECLARE
            canonical bytea;
            tbl regclass;
            row_item gate.row_payload;
            total integer := 0;
            row_count integer;
        BEGIN
            IF p_operation <> 'insert' THEN
                RAISE EXCEPTION 'unsupported_operation';
            END IF;

            canonical := gate._canonical_batch(p_table, p_operation, p_locator, p_rows);
            PERFORM gate._assert_signature(canonical, p_signature);

            IF p_table NOT IN ('scrape_logs', 'api_logs') THEN
                RAISE EXCEPTION 'unsupported_operation';
            END IF;

            tbl := to_regclass(format('public.%I', p_table));
            IF tbl IS NULL THEN
                RAISE EXCEPTION 'unsupported_operation';
            END IF;

            IF p_rows IS NOT NULL THEN
                FOREACH row_item IN ARRAY p_rows LOOP
                    row_count := gate._insert_from_entries(tbl, row_item.fields);
                    total := total + row_count;
                END LOOP;
            END IF;
            RETURN total;
        END;
        $fn$;
        """
    )
    _revoke(
        "FUNCTION gate.exec_write_batch(text, text, gate.field_entry[], gate.row_payload[], text)"
    )


def downgrade() -> None:
    _create("DROP FUNCTION IF EXISTS gate.exec_write_batch(text, text, gate.field_entry[], gate.row_payload[], text);")
    _create("DROP FUNCTION IF EXISTS gate.exec_write(text, text, gate.field_entry[], gate.field_entry[], text);")
    _create("DROP FUNCTION IF EXISTS gate._locator_keys(text);")
    _create("DROP FUNCTION IF EXISTS gate._operation_allowed(text, text);")
    _create("DROP FUNCTION IF EXISTS gate._insert_dim_date(gate.field_entry[]);")
    _create("DROP FUNCTION IF EXISTS gate._retention_delete(regclass, gate.field_entry[]);")
    _create("DROP FUNCTION IF EXISTS gate._delete_from_locator(regclass, text[], gate.field_entry[]);")
    _create("DROP FUNCTION IF EXISTS gate._update_from_entries(regclass, text[], gate.field_entry[], gate.field_entry[]);")
    _create("DROP FUNCTION IF EXISTS gate._insert_from_entries(regclass, gate.field_entry[]);")
    _create("DROP FUNCTION IF EXISTS gate._typed_literal(regclass, text, boolean, text);")
    _create("DROP FUNCTION IF EXISTS gate._entry_is_null(gate.field_entry[], text);")
    _create("DROP FUNCTION IF EXISTS gate._entry_text(gate.field_entry[], text);")
    _create("DROP FUNCTION IF EXISTS gate._assert_signature(bytea, text);")
    _create("DROP FUNCTION IF EXISTS gate._hmac_hex(bytea);")
    _create("DROP FUNCTION IF EXISTS gate._signing_secret();")
    _create("DROP FUNCTION IF EXISTS gate._canonical_batch(text, text, gate.field_entry[], gate.row_payload[]);")
    _create("DROP FUNCTION IF EXISTS gate._canonical_record(text, text, gate.field_entry[], gate.field_entry[]);")
    _create("DROP FUNCTION IF EXISTS gate._dict_enc(gate.field_entry[]);")
    _create("DROP FUNCTION IF EXISTS gate._val_enc(boolean, text);")
    _create("DROP FUNCTION IF EXISTS gate._lp_string(text);")
    _create("DROP TYPE IF EXISTS gate.row_payload;")
    _create("DROP TYPE IF EXISTS gate.field_entry;")
    _create("DROP SCHEMA IF EXISTS gate;")
