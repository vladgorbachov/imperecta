"""Legal clean-up WP1: purge RU / BY / KZ from the data, drop regions.

Revision ID: 071_legal_purge_ru_by_kz
Revises: 070_drop_duplicate_indexes
Create Date: 2026-09-19

Founder's decision of 2026-09-19 (docs/LEGAL_CLEANUP_PLAN_2026-09-19.md,
counsel's memo §2.9 / §3.11): Russia, Belarus and Kazakhstan leave the
product completely — marketplaces WITH all their data, countries,
currencies — and the product knows countries only, nothing above them
(§1.3: no regions).

Two pieces, both idempotent:

1. `maintenance.purge_marketplace(marketplace_id, dry_run)` — the ONE
   routine that deletes a source with everything it produced, in FK order,
   returning the counts as jsonb. WP5 reuses it for opt-out / cease-and-
   desist and for the admin "delete" (which today only drops the dimension
   row and leaves orphan products and Redis state behind). Set-based
   deletes on a temp list of listing ids instead of 200k cascades; orphan
   products = products no other marketplace's listing references (the
   Scrape L2 prune rule). user_products rows on those products go with them
   (CASCADE) and are counted.

2. The purge itself: marketplaces selected by country, by host TLD
   (.ru/.by/.kz/.su/.рф — derived from domain/base_url, not country_code,
   the two can disagree) and by a hard host list; then every row that still
   references the three countries or currencies; then the country and
   currency rows; then `dim_country.region` / `subregion` are dropped and
   the materialised views refreshed. The seed migrations (001/009) are
   history and stay untouched; a fresh schema ends without RU/BY/KZ and
   RUB/BYN/KZT because this migration runs after them.

Irreversible by design: the founder confirms a Supabase backup / PITR point
before this is deployed (plan §0). Downgrade recreates only the region
columns (nullable) — the data is gone.
"""

from __future__ import annotations

from alembic import op

revision = "071_legal_purge_ru_by_kz"
down_revision = "070_drop_duplicate_indexes"
branch_labels = None
depends_on = None

_SEARCH_PATH = "SET search_path = pg_catalog, public, pg_temp"
_ROUTINE = "maintenance.purge_marketplace(uuid, boolean)"

PURGED_COUNTRIES = ("RU", "BY", "KZ")
PURGED_CURRENCIES = ("RUB", "BYN", "KZT")
# Host TLDs of the purged jurisdictions (matched on domain AND base_url).
PURGED_TLD_RE = r"\.(ru|by|kz|su|рф)$"
# Hard host list (counsel's memo): matched as a substring of the domain.
PURGED_HOSTS_RE = (
    r"(kaspi\.kz|mechta\.kz|wildberries\.|ozon\.|market\.yandex\.|dns-shop\.|"
    r"citilink\.|mvideo\.|eldorado\.ru|21vek\.by|onliner\.by|e-katalog\.)"
)


def _sql_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    # The purge and the plain MV refreshes outlive the 60 s session default.
    op.execute("SET LOCAL statement_timeout = '20min';")
    op.execute("CREATE SCHEMA IF NOT EXISTS maintenance AUTHORIZATION postgres;")

    # ------------------------------------------------------------------ 1
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION maintenance.purge_marketplace(
            p_marketplace_id uuid,
            p_dry_run boolean DEFAULT true
        )
        RETURNS jsonb
        LANGUAGE plpgsql
        SECURITY DEFINER
        {_SEARCH_PATH}
        AS $fn$
        DECLARE
            v_code text;
            v_domain text;
            c_listings bigint;
            c_products bigint;
            c_user_products bigint;
            c_prices bigint;
            c_weekly bigint;
            c_reviews bigint;
            c_logs bigint;
            c_rejects bigint;
            c_sellers bigint;
            c_promos bigint;
            c_digests bigint;
            n bigint;
        BEGIN
            SELECT marketplace_code, domain INTO v_code, v_domain
            FROM dim_marketplace WHERE id = p_marketplace_id;
            IF v_code IS NULL THEN
                RETURN jsonb_build_object(
                    'status', 'not_found', 'marketplace_id', p_marketplace_id
                );
            END IF;

            -- One call may run several times inside one transaction (the
            -- RU/BY/KZ migration loops over marketplaces): reuse the temp
            -- tables, ON COMMIT DROP cleans up.
            CREATE TEMP TABLE IF NOT EXISTS _purge_listings (
                id uuid PRIMARY KEY, product_id uuid
            ) ON COMMIT DROP;
            CREATE TEMP TABLE IF NOT EXISTS _purge_products (
                id uuid PRIMARY KEY
            ) ON COMMIT DROP;
            TRUNCATE _purge_listings;
            TRUNCATE _purge_products;

            INSERT INTO _purge_listings (id, product_id)
            SELECT id, product_id FROM fact_listing
            WHERE marketplace_id = p_marketplace_id;

            -- Orphans: products no listing of ANOTHER marketplace references.
            INSERT INTO _purge_products (id)
            SELECT DISTINCT pl.product_id FROM _purge_listings pl
            WHERE pl.product_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM fact_listing l
                  WHERE l.product_id = pl.product_id
                    AND l.marketplace_id <> p_marketplace_id
              );

            SELECT count(*) INTO c_listings FROM _purge_listings;
            SELECT count(*) INTO c_products FROM _purge_products;
            SELECT count(*) INTO c_user_products FROM user_products
            WHERE product_id IN (SELECT id FROM _purge_products);
            SELECT count(*) INTO c_prices FROM fact_price
            WHERE listing_id IN (SELECT id FROM _purge_listings);
            SELECT count(*) INTO c_weekly FROM fact_price_weekly
            WHERE listing_id IN (SELECT id FROM _purge_listings);
            SELECT count(*) INTO c_reviews FROM fact_review
            WHERE listing_id IN (SELECT id FROM _purge_listings);
            SELECT count(*) INTO c_logs FROM scrape_logs
            WHERE marketplace_id = p_marketplace_id
               OR listing_id IN (SELECT id FROM _purge_listings);
            SELECT count(*) INTO c_rejects FROM reject_data
            WHERE marketplace_id = p_marketplace_id
               OR listing_id IN (SELECT id FROM _purge_listings);
            SELECT count(*) INTO c_sellers FROM dim_seller
            WHERE marketplace_id = p_marketplace_id;
            SELECT count(*) INTO c_promos FROM fact_promo
            WHERE marketplace_id = p_marketplace_id
               OR listing_id IN (SELECT id FROM _purge_listings);
            SELECT count(*) INTO c_digests FROM digests
            WHERE p_marketplace_id = ANY(marketplace_ids);

            IF p_dry_run THEN
                RETURN jsonb_build_object(
                    'status', 'dry_run',
                    'marketplace_id', p_marketplace_id,
                    'marketplace_code', v_code,
                    'domain', v_domain,
                    'listings', c_listings,
                    'products', c_products,
                    'user_products', c_user_products,
                    'prices', c_prices,
                    'prices_weekly', c_weekly,
                    'reviews', c_reviews,
                    'scrape_logs', c_logs,
                    'reject_data', c_rejects,
                    'sellers', c_sellers,
                    'promos', c_promos,
                    'digests_unlinked', c_digests
                );
            END IF;

            -- FK order: children of fact_listing first (set-based, no
            -- per-row cascades), then the listings, then what only they
            -- referenced, then the dimension row.
            DELETE FROM fact_price
            WHERE listing_id IN (SELECT id FROM _purge_listings);
            GET DIAGNOSTICS n = ROW_COUNT; c_prices := n;
            DELETE FROM fact_price_weekly
            WHERE listing_id IN (SELECT id FROM _purge_listings);
            GET DIAGNOSTICS n = ROW_COUNT; c_weekly := n;
            DELETE FROM fact_review
            WHERE listing_id IN (SELECT id FROM _purge_listings);
            GET DIAGNOSTICS n = ROW_COUNT; c_reviews := n;
            DELETE FROM scrape_logs
            WHERE marketplace_id = p_marketplace_id
               OR listing_id IN (SELECT id FROM _purge_listings);
            GET DIAGNOSTICS n = ROW_COUNT; c_logs := n;
            DELETE FROM reject_data
            WHERE marketplace_id = p_marketplace_id
               OR listing_id IN (SELECT id FROM _purge_listings);
            GET DIAGNOSTICS n = ROW_COUNT; c_rejects := n;
            DELETE FROM fact_promo
            WHERE marketplace_id = p_marketplace_id
               OR listing_id IN (SELECT id FROM _purge_listings);
            GET DIAGNOSTICS n = ROW_COUNT; c_promos := n;
            -- alerts / alert_events keep their rows (user data) and lose
            -- the pointer through their SET NULL foreign keys.
            UPDATE digests
            SET marketplace_ids = array_remove(marketplace_ids, p_marketplace_id)
            WHERE p_marketplace_id = ANY(marketplace_ids);
            GET DIAGNOSTICS n = ROW_COUNT; c_digests := n;

            DELETE FROM fact_listing WHERE marketplace_id = p_marketplace_id;
            GET DIAGNOSTICS n = ROW_COUNT; c_listings := n;
            DELETE FROM dim_seller WHERE marketplace_id = p_marketplace_id;
            GET DIAGNOSTICS n = ROW_COUNT; c_sellers := n;
            DELETE FROM dim_product
            WHERE id IN (SELECT id FROM _purge_products);
            GET DIAGNOSTICS n = ROW_COUNT; c_products := n;
            -- scrape_jobs.marketplace_id and alerts.marketplace_id are
            -- SET NULL foreign keys.
            DELETE FROM dim_marketplace WHERE id = p_marketplace_id;

            RETURN jsonb_build_object(
                'status', 'purged',
                'marketplace_id', p_marketplace_id,
                'marketplace_code', v_code,
                'domain', v_domain,
                'listings', c_listings,
                'products', c_products,
                'user_products', c_user_products,
                'prices', c_prices,
                'prices_weekly', c_weekly,
                'reviews', c_reviews,
                'scrape_logs', c_logs,
                'reject_data', c_rejects,
                'sellers', c_sellers,
                'promos', c_promos,
                'digests_unlinked', c_digests
            );
        END;
        $fn$;
        """
    )
    op.execute(f"REVOKE EXECUTE ON FUNCTION {_ROUTINE} FROM PUBLIC;")

    # ------------------------------------------------------------------ 2
    countries = _sql_list(PURGED_COUNTRIES)
    currencies = _sql_list(PURGED_CURRENCIES)
    op.execute(
        f"""
        DO $purge$
        DECLARE
            r record;
            res jsonb;
            total integer := 0;
        BEGIN
            FOR r IN
                SELECT id, marketplace_code, domain
                FROM dim_marketplace
                WHERE country_code IN ({countries})
                   OR lower(domain) ~ '{PURGED_TLD_RE}'
                   OR lower(regexp_replace(base_url, '^https?://([^/]+).*$', '\\1'))
                      ~ '{PURGED_TLD_RE}'
                   OR lower(domain) ~ '{PURGED_HOSTS_RE}'
                ORDER BY marketplace_code
            LOOP
                res := maintenance.purge_marketplace(r.id, false);
                total := total + 1;
                RAISE NOTICE 'legal purge: % (%) -> %', r.marketplace_code, r.domain, res;
            END LOOP;
            RAISE NOTICE 'legal purge: % marketplace(s) removed', total;
        END
        $purge$;
        """
    )

    # Rows still pointing at the countries / currencies (RESTRICT and
    # NO ACTION foreign keys), then the reference rows themselves.
    op.execute(f"UPDATE alerts SET country_code = NULL WHERE country_code IN ({countries});")
    op.execute(
        f"""
        UPDATE digests
        SET country_codes = ARRAY(
            SELECT c FROM unnest(country_codes) AS c WHERE c NOT IN ({countries})
        )
        WHERE country_codes && ARRAY[{countries}]::varchar[];
        """
    )
    op.execute(f"UPDATE dim_brand SET country_code = NULL WHERE country_code IN ({countries});")
    op.execute(
        f"DELETE FROM fact_fuel_price WHERE country_code IN ({countries}) "
        f"OR currency_code IN ({currencies});"
    )
    op.execute(f"DELETE FROM fact_search_trend WHERE country_code IN ({countries});")
    op.execute(
        f"DELETE FROM fact_tariff WHERE origin_country IN ({countries}) "
        f"OR destination_country IN ({countries});"
    )
    op.execute(f"DELETE FROM dim_country WHERE country_code IN ({countries});")
    op.execute(f"DELETE FROM fact_currency_rate WHERE currency_code IN ({currencies});")
    op.execute(f"DELETE FROM dim_currency WHERE currency_code IN ({currencies});")

    # §1.3 — countries only, nothing above them.
    op.execute("ALTER TABLE dim_country DROP CONSTRAINT IF EXISTS ck_dim_country_region;")
    op.execute("ALTER TABLE dim_country DROP COLUMN IF EXISTS region;")
    op.execute("ALTER TABLE dim_country DROP COLUMN IF EXISTS subregion;")

    for mv in (
        "mv_marketplace_stats",
        "mv_pool_stats",
        "mv_daily_price_summary",
        "mv_marketplace_health",
    ):
        op.execute(f"REFRESH MATERIALIZED VIEW {mv};")


def downgrade() -> None:
    op.execute("ALTER TABLE dim_country ADD COLUMN IF NOT EXISTS region VARCHAR(30);")
    op.execute("ALTER TABLE dim_country ADD COLUMN IF NOT EXISTS subregion VARCHAR(50);")
    op.execute(f"DROP FUNCTION IF EXISTS {_ROUTINE};")
