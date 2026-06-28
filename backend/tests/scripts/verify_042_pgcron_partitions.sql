-- DB-required verification for migration 042_pgcron_fact_price_partitions (E1).
-- Structural checks: any role with catalog read access.
-- Helper + functional tests: run as postgres (or superuser).
--
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
--     -f backend/tests/scripts/verify_042_pgcron_partitions.sql

\set ON_ERROR_STOP on

-- === Structural (any read role) ===

DO $$
BEGIN
    IF to_regprocedure('maintenance._ensure_fact_price_partition(integer, integer)') IS NULL THEN
        RAISE EXCEPTION 'maintenance._ensure_fact_price_partition(int,int) missing';
    END IF;

    IF to_regprocedure('maintenance.ensure_fact_price_partitions()') IS NULL THEN
        RAISE EXCEPTION 'maintenance.ensure_fact_price_partitions() missing';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_proc AS p
        JOIN pg_namespace AS n ON n.oid = p.pronamespace
        WHERE n.nspname = 'maintenance'
          AND p.proname = '_ensure_fact_price_partition'
          AND p.prosecdef = true
    ) THEN
        RAISE EXCEPTION '_ensure_fact_price_partition is not SECURITY DEFINER';
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

    IF has_function_privilege(
        'public',
        'maintenance._ensure_fact_price_partition(integer, integer)',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'PUBLIC still has EXECUTE on _ensure_fact_price_partition';
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

-- === Helper functional test on throwaway months (postgres) ===

DO $$
DECLARE
    bound_expr text;
    parent_name text;
BEGIN
    IF NOT pg_has_role(current_user, 'pg_superuser', 'MEMBER')
       AND current_user <> 'postgres' THEN
        RAISE NOTICE 'Skipping helper functional test — connect as postgres';
        RETURN;
    END IF;

    PERFORM maintenance._ensure_fact_price_partition(2099, 1);

    IF to_regclass('public.fact_price_209901') IS NULL THEN
        RAISE EXCEPTION 'fact_price_209901 not created';
    END IF;

    SELECT pg_get_expr(c.relpartbound, c.oid, true), parent.relname
    INTO bound_expr, parent_name
    FROM pg_class AS c
    JOIN pg_namespace AS n ON n.oid = c.relnamespace
    JOIN pg_inherits AS inh ON inh.inhrelid = c.oid
    JOIN pg_class AS parent ON parent.oid = inh.inhparent
    WHERE n.nspname = 'public'
      AND c.relname = 'fact_price_209901';

    IF parent_name <> 'fact_price' THEN
        RAISE EXCEPTION 'fact_price_209901 parent expected fact_price, got %', parent_name;
    END IF;

    IF bound_expr NOT LIKE '%20990101%' OR bound_expr NOT LIKE '%20990201%' THEN
        RAISE EXCEPTION 'fact_price_209901 bounds unexpected: %', bound_expr;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_class AS c
        JOIN pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relname = 'fact_price_209901'
          AND c.relrowsecurity = true
    ) THEN
        RAISE EXCEPTION 'fact_price_209901 missing RLS';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'fact_price_209901'
          AND policyname = 'rls_deny_client_roles'
    ) THEN
        RAISE EXCEPTION 'fact_price_209901 missing rls_deny_client_roles';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'fact_price_209901'
          AND policyname = 'rls_app_read'
    ) THEN
        RAISE EXCEPTION 'fact_price_209901 missing rls_app_read';
    END IF;

    PERFORM maintenance._ensure_fact_price_partition(2099, 12);

    SELECT pg_get_expr(c.relpartbound, c.oid, true)
    INTO bound_expr
    FROM pg_class AS c
    JOIN pg_namespace AS n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relname = 'fact_price_209912';

    IF bound_expr NOT LIKE '%20991201%' OR bound_expr NOT LIKE '%21000101%' THEN
        RAISE EXCEPTION 'fact_price_209912 December rollover bounds unexpected: %', bound_expr;
    END IF;

    DROP TABLE IF EXISTS public.fact_price_209901;
    DROP TABLE IF EXISTS public.fact_price_209912;

    RAISE NOTICE 'verify_042 helper functional: 209901 + 209912 rollover OK';
END
$$;

-- === Scheduled wrapper functional (+1/+2/+3 months) ===

DO $$
DECLARE
    cy integer;
    cm integer;
    i integer;
    offset_months integer;
    pname text;
    missing_policy_count integer := 0;
BEGIN
    IF NOT pg_has_role(current_user, 'pg_superuser', 'MEMBER')
       AND current_user <> 'postgres' THEN
        RAISE NOTICE 'Skipping scheduled wrapper functional — connect as postgres';
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
            RAISE EXCEPTION 'expected partition public.% missing after wrapper run', pname;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE schemaname = 'public'
              AND tablename = pname
              AND policyname = 'rls_app_read'
        ) THEN
            missing_policy_count := missing_policy_count + 1;
        END IF;
    END LOOP;

    IF missing_policy_count > 0 THEN
        RAISE EXCEPTION
            'rls_app_read missing on % of 3 rolling partitions', missing_policy_count;
    END IF;

    RAISE NOTICE 'verify_042 wrapper functional: +1/+2/+3 partitions OK';
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
