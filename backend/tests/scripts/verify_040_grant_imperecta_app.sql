-- DB-required verification for migration 040_grant_imperecta_app (seam 9.3).
-- Run after `alembic upgrade head` on a dev-branch or local Postgres:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/tests/scripts/verify_040_grant_imperecta_app.sql
--
-- Asserts imperecta_app least-privilege grants are present and idle gate helpers
-- remain unreachable. Safe to re-run (read-only checks).

\set ON_ERROR_STOP on

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'imperecta_app') THEN
        RAISE EXCEPTION 'role imperecta_app missing (run migration 038 first)';
    END IF;
END
$$;

-- (1) EXECUTE on gate entry points
DO $$
BEGIN
    IF NOT has_function_privilege(
        'imperecta_app',
        'gate.exec_write(text, text, gate.field_entry[], gate.field_entry[], text)',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'imperecta_app missing EXECUTE on gate.exec_write';
    END IF;
    IF NOT has_function_privilege(
        'imperecta_app',
        'gate.exec_write_batch(text, text, gate.field_entry[], gate.row_payload[], text)',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'imperecta_app missing EXECUTE on gate.exec_write_batch';
    END IF;
END
$$;

-- (2) NOT EXECUTE on internal helper sample
DO $$
BEGIN
    IF has_function_privilege(
        'imperecta_app',
        'gate._canonical_record(text, text, gate.field_entry[], gate.field_entry[])',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'imperecta_app must NOT have EXECUTE on gate._canonical_record';
    END IF;
END
$$;

-- (3) SELECT on sample tables
DO $$
DECLARE
    sample_tables text[] := ARRAY[
        'users', 'fact_listing', 'dim_product', 'scrape_logs', 'reject_data'
    ];
    tbl text;
BEGIN
    FOREACH tbl IN ARRAY sample_tables LOOP
        IF to_regclass('public.' || tbl) IS NULL THEN
            RAISE EXCEPTION 'expected table public.% missing', tbl;
        END IF;
        IF NOT has_table_privilege('imperecta_app', 'public.' || tbl, 'SELECT') THEN
            RAISE EXCEPTION 'imperecta_app missing SELECT on %', tbl;
        END IF;
    END LOOP;
END
$$;

-- (4) INSERT only on reject_data
DO $$
DECLARE
    extra_insert_count integer;
BEGIN
    SELECT count(*) INTO extra_insert_count
    FROM information_schema.table_privileges
    WHERE grantee = 'imperecta_app'
      AND table_schema = 'public'
      AND privilege_type = 'INSERT'
      AND table_name <> 'reject_data';

    IF extra_insert_count > 0 THEN
        RAISE EXCEPTION
            'imperecta_app has INSERT on % table(s) other than reject_data',
            extra_insert_count;
    END IF;

    IF NOT has_table_privilege('imperecta_app', 'public.reject_data', 'INSERT') THEN
        RAISE EXCEPTION 'imperecta_app missing INSERT on reject_data carve-out';
    END IF;
END
$$;

-- (5) rls_app_read on every public RLS table (ordinary + partitioned parents)
DO $$
DECLARE
    missing_count integer;
    rls_count integer;
BEGIN
    SELECT count(*) INTO rls_count
    FROM pg_class AS c
    JOIN pg_namespace AS n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relkind IN ('r', 'p')
      AND c.relrowsecurity = true;

    SELECT count(*) INTO missing_count
    FROM pg_class AS c
    JOIN pg_namespace AS n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relkind IN ('r', 'p')
      AND c.relrowsecurity = true
      AND NOT EXISTS (
          SELECT 1
          FROM pg_policies AS p
          WHERE p.schemaname = 'public'
            AND p.tablename = c.relname
            AND p.policyname = 'rls_app_read'
      );

    IF missing_count > 0 THEN
        RAISE EXCEPTION
            'rls_app_read missing on % of % RLS tables (relkind r+p)',
            missing_count, rls_count;
    END IF;

    RAISE NOTICE 'rls_app_read present on all % RLS-enabled public tables (r+p)', rls_count;
END
$$;

-- (6) service_alerts excluded from RLS (no rls_app_read expected)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_class AS c
        JOIN pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relname = 'service_alerts'
          AND c.relrowsecurity = true
    ) THEN
        RAISE EXCEPTION 'service_alerts unexpectedly has RLS enabled';
    END IF;
END
$$;

-- (7) rls_app_reject_insert carve-out policy
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_policies AS p
        WHERE p.schemaname = 'public'
          AND p.tablename = 'reject_data'
          AND p.policyname = 'rls_app_reject_insert'
    ) THEN
        RAISE EXCEPTION 'rls_app_reject_insert policy missing on reject_data';
    END IF;
END
$$;

-- (8) sequence USAGE
DO $$
DECLARE
    seq_name text;
    required_seqs text[] := ARRAY['ai_chat_messages_id_seq', 'reject_data_id_seq'];
BEGIN
    FOREACH seq_name IN ARRAY required_seqs LOOP
        IF to_regclass('public.' || seq_name) IS NULL THEN
            RAISE EXCEPTION 'expected sequence public.% missing', seq_name;
        END IF;
        IF NOT has_sequence_privilege('imperecta_app', 'public.' || seq_name, 'USAGE') THEN
            RAISE EXCEPTION 'imperecta_app missing USAGE on sequence %', seq_name;
        END IF;
    END LOOP;
END
$$;

\echo 'verify_040_grant_imperecta_app: all checks passed'
