-- DB-required verification for migration 042_pgcron_fact_price_partitions (E1).
-- Structural checks: any role with catalog read access.
-- Functional + rehearsal: run as postgres (or superuser).
--
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
--     -f backend/tests/scripts/verify_042_pgcron_partitions.sql
--
-- Operator must run SELECT maintenance.ensure_fact_price_partitions() once after
-- deploy (or wait for the 00:00 UTC pg_cron tick) before functional asserts pass.

\set ON_ERROR_STOP on

-- === Structural (any read role) ===

DO $$
BEGIN
    IF to_regprocedure('maintenance.ensure_fact_price_partitions()') IS NULL THEN
        RAISE EXCEPTION 'maintenance.ensure_fact_price_partitions() missing';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_proc AS p
        JOIN pg_namespace AS n ON n.oid = p.pronamespace
        WHERE n.nspname = 'maintenance'
          AND p.proname = 'ensure_fact_price_partitions'
          AND p.prosecdef = true
    ) THEN
        RAISE EXCEPTION 'ensure_fact_price_partitions is not SECURITY DEFINER';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_proc AS p
        JOIN pg_namespace AS n ON n.oid = p.pronamespace
        JOIN pg_roles AS r ON r.oid = p.proowner
        WHERE n.nspname = 'maintenance'
          AND p.proname = 'ensure_fact_price_partitions'
          AND r.rolname = 'postgres'
    ) THEN
        RAISE EXCEPTION 'ensure_fact_price_partitions owner is not postgres';
    END IF;

    IF has_function_privilege(
        'public',
        'maintenance.ensure_fact_price_partitions()',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'PUBLIC still has EXECUTE on ensure_fact_price_partitions';
    END IF;
END
$$;

DO $$
DECLARE
    job_schedule text;
    job_command text;
    job_username text;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
        RAISE EXCEPTION 'pg_cron extension not installed';
    END IF;

    SELECT schedule, command, username
    INTO job_schedule, job_command, job_username
    FROM cron.job
    WHERE jobname = 'ensure-fact-price-partitions';

    IF job_schedule IS NULL THEN
        RAISE EXCEPTION 'cron job ensure-fact-price-partitions missing';
    END IF;

    IF job_schedule <> '0 0 * * *' THEN
        RAISE EXCEPTION 'unexpected cron schedule: %', job_schedule;
    END IF;

    IF job_command <> 'SELECT maintenance.ensure_fact_price_partitions()' THEN
        RAISE EXCEPTION 'unexpected cron command: %', job_command;
    END IF;

    IF job_username <> 'postgres' THEN
        RAISE EXCEPTION 'cron job username expected postgres, got %', job_username;
    END IF;
END
$$;

\echo 'verify_042 structural checks passed (any role)'

-- === Functional (postgres / superuser) ===
-- Uncomment or run the block below manually when connected as postgres.

DO $$
DECLARE
    cy integer;
    cm integer;
    ny integer;
    nm integer;
    i integer;
    offset_months integer;
    pname text;
    missing_policy_count integer := 0;
BEGIN
    IF NOT pg_has_role(current_user, 'pg_superuser', 'MEMBER')
       AND current_user <> 'postgres' THEN
        RAISE NOTICE 'Skipping functional partition asserts — connect as postgres';
        RETURN;
    END IF;

    PERFORM maintenance.ensure_fact_price_partitions();

    FOR offset_months IN 1..3 LOOP
        cy := EXTRACT(YEAR FROM (timezone('UTC', now())))::integer;
        cm := EXTRACT(MONTH FROM (timezone('UTC', now())))::integer;

        FOR i IN 1..offset_months LOOP
            IF cm = 12 THEN
                cy := cy + 1;
                cm := 1;
            ELSE
                cm := cm + 1;
            END IF;
        END LOOP;

        pname := 'fact_price_' || cy::text || lpad(cm::text, 2, '0');

        IF to_regclass('public.' || pname) IS NULL THEN
            RAISE EXCEPTION 'expected partition public.% missing after routine run', pname;
        END IF;

        IF NOT EXISTS (
            SELECT 1
            FROM pg_class AS c
            JOIN pg_namespace AS n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relname = pname
              AND c.relkind = 'r'
              AND c.relrowsecurity = true
        ) THEN
            RAISE EXCEPTION 'partition % missing RLS', pname;
        END IF;

        IF NOT EXISTS (
            SELECT 1
            FROM pg_policies AS p
            WHERE p.schemaname = 'public'
              AND p.tablename = pname
              AND p.policyname = 'rls_app_read'
        ) THEN
            missing_policy_count := missing_policy_count + 1;
        END IF;
    END LOOP;

    IF missing_policy_count > 0 THEN
        RAISE EXCEPTION
            'rls_app_read missing on % of 3 rolling partitions', missing_policy_count;
    END IF;

    RAISE NOTICE 'verify_042 functional: +1/+2/+3 partitions exist with rls_app_read';
END
$$;

-- === Rehearsal gate (postgres runs SET ROLE) ===

DO $$
DECLARE
    fact_price_count bigint;
    users_count bigint;
BEGIN
    IF NOT pg_has_role(current_user, 'pg_superuser', 'MEMBER')
       AND current_user <> 'postgres' THEN
        RAISE NOTICE 'Skipping imperecta_app rehearsal — connect as postgres';
        RETURN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'imperecta_app') THEN
        RAISE EXCEPTION 'role imperecta_app missing (run migration 040 first)';
    END IF;

    EXECUTE 'SET ROLE imperecta_app';
    SELECT count(*) INTO fact_price_count FROM fact_price;
    SELECT count(*) INTO users_count FROM users;
    EXECUTE 'RESET ROLE';

    IF fact_price_count = 0 THEN
        RAISE EXCEPTION
            'imperecta_app sees 0 rows in fact_price after partition routine';
    END IF;

    IF users_count = 0 THEN
        RAISE EXCEPTION 'imperecta_app sees 0 rows in users (control)';
    END IF;

    RAISE NOTICE 'verify_042 rehearsal: imperecta_app fact_price=% users=%',
        fact_price_count, users_count;
END
$$;

\echo 'verify_042_pgcron_partitions: all applicable checks passed'
