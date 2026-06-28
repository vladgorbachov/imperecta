-- DB-required verification for migration 041 (seam 9.3 fix).
-- Run after `alembic upgrade head` on dev-branch or prod rehearsal:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
--     -f backend/tests/scripts/verify_041_partition_parent_rls.sql
--
-- Asserts relkind='p' RLS parents have rls_app_read and imperecta_app can SELECT
-- fact_price rows. Safe to re-run.

\set ON_ERROR_STOP on

-- (1) relkind='p' RLS parents must have rls_app_read (expect fact_price)
DO $$
DECLARE
    missing_count integer;
    parent_count integer;
    parent_name text;
BEGIN
    SELECT count(*) INTO parent_count
    FROM pg_class AS c
    JOIN pg_namespace AS n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relkind = 'p'
      AND c.relrowsecurity = true;

    SELECT count(*) INTO missing_count
    FROM pg_class AS c
    JOIN pg_namespace AS n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relkind = 'p'
      AND c.relrowsecurity = true
      AND NOT EXISTS (
          SELECT 1
          FROM pg_policies AS p
          WHERE p.schemaname = 'public'
            AND p.tablename = c.relname
            AND p.policyname = 'rls_app_read'
      );

    IF missing_count > 0 THEN
        FOR parent_name IN
            SELECT c.relname
            FROM pg_class AS c
            JOIN pg_namespace AS n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relkind = 'p'
              AND c.relrowsecurity = true
              AND NOT EXISTS (
                  SELECT 1
                  FROM pg_policies AS p
                  WHERE p.schemaname = 'public'
                    AND p.tablename = c.relname
                    AND p.policyname = 'rls_app_read'
              )
        LOOP
            RAISE EXCEPTION 'rls_app_read missing on partitioned parent %', parent_name;
        END LOOP;
    END IF;

    RAISE NOTICE 'rls_app_read present on all % relkind=p RLS parents', parent_count;
END
$$;

-- (2) relkind-complete: every public RLS object (r + p) has rls_app_read
DO $$
DECLARE
    missing_count integer;
BEGIN
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
            'rls_app_read missing on % RLS tables (relkind r+p)', missing_count;
    END IF;
END
$$;

-- (3) Runtime gate for 9.4/9.5 rehearsal: imperecta_app must see rows
DO $$
DECLARE
    fact_price_count bigint;
    users_count bigint;
BEGIN
    IF to_regclass('public.fact_price') IS NULL THEN
        RAISE EXCEPTION 'fact_price table missing';
    END IF;

    EXECUTE 'SET ROLE imperecta_app';
    SELECT count(*) INTO fact_price_count FROM fact_price;
    SELECT count(*) INTO users_count FROM users;
    EXECUTE 'RESET ROLE';

    IF fact_price_count = 0 THEN
        RAISE EXCEPTION
            'imperecta_app sees 0 rows in fact_price (rls_app_read on parent missing?)';
    END IF;

    IF users_count = 0 THEN
        RAISE EXCEPTION
            'imperecta_app sees 0 rows in users (control check failed)';
    END IF;

    RAISE NOTICE 'imperecta_app runtime: fact_price=% rows, users=% rows',
        fact_price_count, users_count;
END
$$;

\echo 'verify_041_partition_parent_rls: all checks passed'
