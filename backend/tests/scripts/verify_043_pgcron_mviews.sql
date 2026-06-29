-- DB-required verification for migration 043_pgcron_refresh_mviews (E2).
-- Structural checks: any role with catalog read access.
-- Functional test: run as postgres (or superuser).
--
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
--     -f backend/tests/scripts/verify_043_pgcron_mviews.sql

\set ON_ERROR_STOP on

-- === Structural (any read role) ===

DO $$
BEGIN
    IF to_regprocedure('maintenance.refresh_materialized_views()') IS NULL THEN
        RAISE EXCEPTION 'maintenance.refresh_materialized_views() missing';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_proc AS p
        JOIN pg_namespace AS n ON n.oid = p.pronamespace
        WHERE n.nspname = 'maintenance'
          AND p.proname = 'refresh_materialized_views'
          AND p.prosecdef = true
    ) THEN
        RAISE EXCEPTION 'refresh_materialized_views is not SECURITY DEFINER';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_proc AS p
        JOIN pg_namespace AS n ON n.oid = p.pronamespace
        WHERE n.nspname = 'maintenance'
          AND p.proname = 'refresh_materialized_views'
          AND pg_get_userbyid(p.proowner) = 'postgres'
    ) THEN
        RAISE EXCEPTION 'refresh_materialized_views owner expected postgres';
    END IF;

    IF has_function_privilege(
        'public',
        'maintenance.refresh_materialized_views()',
        'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'PUBLIC still has EXECUTE on refresh_materialized_views';
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
    WHERE jobname = 'refresh-materialized-views';

    IF job_schedule IS NULL THEN
        RAISE EXCEPTION 'cron job refresh-materialized-views missing';
    END IF;

    IF job_schedule <> '0 * * * *' THEN
        RAISE EXCEPTION 'unexpected cron schedule: %', job_schedule;
    END IF;

    IF job_command <> 'SELECT maintenance.refresh_materialized_views()' THEN
        RAISE EXCEPTION 'unexpected cron command: %', job_command;
    END IF;

    IF job_username <> 'postgres' THEN
        RAISE EXCEPTION 'cron job username expected postgres, got %', job_username;
    END IF;
END
$$;

\echo 'verify_043 structural checks passed (any role)'

-- === Functional (postgres / superuser) ===

DO $$
BEGIN
    IF NOT pg_has_role(current_user, 'pg_superuser', 'MEMBER')
       AND current_user <> 'postgres' THEN
        RAISE NOTICE 'Skipping functional refresh — connect as postgres';
        RETURN;
    END IF;

    PERFORM maintenance.refresh_materialized_views();

    RAISE NOTICE 'verify_043 functional: refresh_materialized_views() completed';
END
$$;

\echo 'verify_043_pgcron_mviews: all applicable checks passed'
