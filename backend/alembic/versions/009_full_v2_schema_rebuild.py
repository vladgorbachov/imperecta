"""Idempotent full v2 star-schema DDL: extensions, 31 public tables, partitions, MVs, seeds.

Safe on Docker and Supabase: no DROP SCHEMA CASCADE. Uses IF NOT EXISTS / ON CONFLICT DO NOTHING.
Complements chain 001–008 when earlier runs stamped revisions without creating objects.
"""

from __future__ import annotations

from collections.abc import Callable

from alembic import op

revision = "009_full_v2_schema_rebuild"
down_revision = "008_fix_alembic_version_length"
branch_labels = None
depends_on = None


def _split_sql_statements(sql: str) -> list[str]:
    """Split SQL batch into single statements, preserving quoted sections (asyncpg)."""
    statements: list[str] = []
    buffer: list[str] = []
    index = 0
    size = len(sql)
    in_single_quote = False
    in_double_quote = False
    dollar_tag: str | None = None

    while index < size:
        char = sql[index]

        if dollar_tag is not None:
            if sql.startswith(dollar_tag, index):
                buffer.append(dollar_tag)
                index += len(dollar_tag)
                dollar_tag = None
                continue
            buffer.append(char)
            index += 1
            continue

        if in_single_quote:
            buffer.append(char)
            if char == "'":
                if index + 1 < size and sql[index + 1] == "'":
                    buffer.append("'")
                    index += 2
                    continue
                in_single_quote = False
            index += 1
            continue

        if in_double_quote:
            buffer.append(char)
            if char == '"':
                if index + 1 < size and sql[index + 1] == '"':
                    buffer.append('"')
                    index += 2
                    continue
                in_double_quote = False
            index += 1
            continue

        if char == "'":
            in_single_quote = True
            buffer.append(char)
            index += 1
            continue

        if char == '"':
            in_double_quote = True
            buffer.append(char)
            index += 1
            continue

        if char == "$":
            probe = index + 1
            while probe < size and (sql[probe].isalnum() or sql[probe] == "_"):
                probe += 1
            if probe < size and sql[probe] == "$":
                tag = sql[index : probe + 1]
                dollar_tag = tag
                buffer.append(tag)
                index = probe + 1
                continue

        if char == ";":
            statement = "".join(buffer).strip()
            if statement:
                statements.append(statement)
            buffer = []
            index += 1
            continue

        buffer.append(char)
        index += 1

    trailing = "".join(buffer).strip()
    if trailing:
        statements.append(trailing)

    return statements


def _run_each(statement: str) -> None:
    """Execute one or more SQL statements (split for asyncpg)."""
    for sql in _split_sql_statements(statement):
        op.execute(sql)


def upgrade() -> None:
    """Create v2 schema objects idempotently."""
    original_execute = op.execute

    def _safe_execute(statement, *args, **kwargs):
        if isinstance(statement, str):
            for sql in _split_sql_statements(statement):
                original_execute(sql, *args, **kwargs)
            return None
        return original_execute(statement, *args, **kwargs)

    op.execute = _safe_execute
    try:
        _upgrade_body(_run_each)
    finally:
        op.execute = original_execute


def _upgrade_body(run: Callable[[str], None]) -> None:
    # --- Extensions & Alembic meta ---
    run(
        """
        CREATE EXTENSION IF NOT EXISTS pg_trgm;
        CREATE EXTENSION IF NOT EXISTS pgcrypto;
        """
    )
    run("DROP EXTENSION IF EXISTS jsonb_plperl;")

    run("CREATE SCHEMA IF NOT EXISTS alembic_meta;")
    run(
        """
        CREATE TABLE IF NOT EXISTS alembic_meta.alembic_version (
            version_num VARCHAR(255) NOT NULL,
            CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
        );
        """
    )

    # --- Dimensions ---
    run(
        """
        CREATE TABLE IF NOT EXISTS dim_date (
            date_id INTEGER PRIMARY KEY,
            full_date DATE UNIQUE NOT NULL,
            year SMALLINT NOT NULL,
            quarter SMALLINT NOT NULL,
            month SMALLINT NOT NULL,
            month_name VARCHAR(20) NOT NULL,
            week_iso SMALLINT NOT NULL,
            day_of_month SMALLINT NOT NULL,
            day_of_week SMALLINT NOT NULL,
            day_name VARCHAR(15) NOT NULL,
            is_weekend BOOLEAN NOT NULL,
            is_last_day_of_month BOOLEAN NOT NULL,
            fiscal_year SMALLINT,
            fiscal_quarter SMALLINT,
            CONSTRAINT ck_dim_date_quarter CHECK (quarter >= 1 AND quarter <= 4),
            CONSTRAINT ck_dim_date_month CHECK (month >= 1 AND month <= 12)
        );
        """
    )
    run("CREATE INDEX IF NOT EXISTS idx_dim_date_full_date ON dim_date (full_date);")

    run(
        """
        CREATE TABLE IF NOT EXISTS dim_currency (
            currency_code VARCHAR(3) PRIMARY KEY,
            name VARCHAR(50) NOT NULL,
            symbol VARCHAR(5) NOT NULL,
            decimal_places SMALLINT DEFAULT 2,
            is_active BOOLEAN DEFAULT true
        );
        """
    )

    run(
        """
        CREATE TABLE IF NOT EXISTS dim_country (
            country_code VARCHAR(2) PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            name_local VARCHAR(100),
            region VARCHAR(30) NOT NULL
                CHECK (region IN (
                    'CIS','EU','EFTA','Balkans','Caucasus','Central_Asia','Turkey','Other'
                )),
            subregion VARCHAR(50),
            currency_code VARCHAR(3) NOT NULL REFERENCES dim_currency(currency_code),
            vat_rate_std NUMERIC(5,2),
            vat_rate_reduced NUMERIC(5,2),
            ecommerce_market_size_eur BIGINT,
            population BIGINT,
            is_active BOOLEAN DEFAULT true
        );
        """
    )

    run(
        """
        CREATE TABLE IF NOT EXISTS dim_marketplace (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            marketplace_code VARCHAR(50) UNIQUE NOT NULL,
            name VARCHAR(200) NOT NULL,
            source_type VARCHAR(30) NOT NULL
                CHECK (source_type IN (
                    'marketplace','price_aggregator','direct_retail','classified',
                    'b2b_platform','brand_store'
                )),
            country_code VARCHAR(2) NOT NULL REFERENCES dim_country(country_code),
            operates_in VARCHAR(2)[] DEFAULT '{}',
            domain VARCHAR(255) NOT NULL,
            base_url TEXT NOT NULL,
            api_available BOOLEAN DEFAULT false,
            api_type VARCHAR(30),
            scraper_type VARCHAR(30) DEFAULT 'web_api'
                CHECK (scraper_type IN (
                    'web_api','playwright','httpx','api_official','rss','feed'
                )),
            currency_code VARCHAR(3) NOT NULL REFERENCES dim_currency(currency_code),
            locale VARCHAR(10),
            is_active BOOLEAN DEFAULT true,
            reliability_score NUMERIC(3,2) DEFAULT 0.00,
            avg_response_ms INTEGER,
            last_scrape_at TIMESTAMPTZ,
            last_scrape_status VARCHAR(20),
            logo_url TEXT,
            monthly_visits BIGINT,
            product_quota INTEGER NOT NULL DEFAULT 0,
            products_in_pool INTEGER NOT NULL DEFAULT 0,
            requires_js BOOLEAN NOT NULL DEFAULT false,
            rate_limit_delay NUMERIC(4,1) NOT NULL DEFAULT 2.0,
            custom_product_link_selector TEXT,
            custom_next_page_selector TEXT,
            custom_price_selector TEXT,
            custom_title_selector TEXT,
            last_discovery_at TIMESTAMPTZ,
            last_discovery_status VARCHAR(20),
            last_discovery_products_found INTEGER NOT NULL DEFAULT 0,
            discovery_error_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        );
        """
    )
    run("CREATE INDEX IF NOT EXISTS idx_marketplace_country ON dim_marketplace (country_code);")
    run("CREATE INDEX IF NOT EXISTS idx_marketplace_type ON dim_marketplace (source_type);")
    run("CREATE INDEX IF NOT EXISTS idx_marketplace_code ON dim_marketplace (marketplace_code);")

    run(
        """
        CREATE TABLE IF NOT EXISTS dim_category (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(200) NOT NULL,
            name_en VARCHAR(200),
            slug VARCHAR(200) UNIQUE NOT NULL,
            parent_id UUID REFERENCES dim_category(id) ON DELETE SET NULL,
            level SMALLINT NOT NULL DEFAULT 1,
            path TEXT NOT NULL,
            hs_code_prefix VARCHAR(10),
            icon VARCHAR(50),
            is_active BOOLEAN DEFAULT true,
            product_count INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT now()
        );
        """
    )
    run("CREATE INDEX IF NOT EXISTS idx_category_parent ON dim_category (parent_id);")
    run(
        "CREATE INDEX IF NOT EXISTS idx_category_path ON dim_category "
        "USING gin (path gin_trgm_ops);"
    )
    run("CREATE INDEX IF NOT EXISTS idx_category_slug ON dim_category (slug);")

    run(
        """
        CREATE TABLE IF NOT EXISTS dim_brand (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(200) NOT NULL,
            slug VARCHAR(200) UNIQUE NOT NULL,
            name_normalized VARCHAR(200) NOT NULL,
            country_code VARCHAR(2) REFERENCES dim_country(country_code),
            website_url TEXT,
            logo_url TEXT,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT now()
        );
        """
    )
    run(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_brand_normalized ON dim_brand (name_normalized);"
    )
    run("CREATE INDEX IF NOT EXISTS idx_brand_slug ON dim_brand (slug);")

    run(
        """
        CREATE TABLE IF NOT EXISTS dim_product (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(500) NOT NULL,
            name_normalized VARCHAR(500) NOT NULL,
            sku_universal VARCHAR(100),
            mpn VARCHAR(100),
            category_id UUID REFERENCES dim_category(id) ON DELETE SET NULL,
            brand_id UUID REFERENCES dim_brand(id) ON DELETE SET NULL,
            attributes JSONB DEFAULT '{}',
            image_url TEXT,
            image_urls TEXT[] DEFAULT '{}',
            hs_code VARCHAR(12),
            weight_kg NUMERIC(10,3),
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        );
        """
    )
    run("CREATE INDEX IF NOT EXISTS idx_product_category ON dim_product (category_id);")
    run("CREATE INDEX IF NOT EXISTS idx_product_brand ON dim_product (brand_id);")
    run(
        "CREATE INDEX IF NOT EXISTS idx_product_name ON dim_product "
        "USING gin (name_normalized gin_trgm_ops);"
    )
    run(
        "CREATE INDEX IF NOT EXISTS idx_product_sku ON dim_product (sku_universal) "
        "WHERE sku_universal IS NOT NULL;"
    )
    run("CREATE INDEX IF NOT EXISTS idx_product_attributes ON dim_product USING gin (attributes);")

    run(
        """
        CREATE TABLE IF NOT EXISTS dim_seller (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(300) NOT NULL,
            name_normalized VARCHAR(300) NOT NULL,
            marketplace_id UUID NOT NULL REFERENCES dim_marketplace(id) ON DELETE CASCADE,
            external_seller_id VARCHAR(200),
            seller_type VARCHAR(30) DEFAULT 'third_party'
                CHECK (seller_type IN ('first_party','third_party','brand_official','unknown')),
            store_url TEXT,
            rating NUMERIC(3,2),
            review_count INTEGER,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        );
        """
    )
    run("CREATE INDEX IF NOT EXISTS idx_seller_marketplace ON dim_seller (marketplace_id);")
    run(
        "CREATE INDEX IF NOT EXISTS idx_seller_external ON dim_seller (marketplace_id, external_seller_id);"
    )
    run(
        "CREATE INDEX IF NOT EXISTS idx_seller_name ON dim_seller "
        "USING gin (name_normalized gin_trgm_ops);"
    )

    # --- Core app users ---
    run(
        """
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            name VARCHAR(100),
            company_name VARCHAR(200),
            plan VARCHAR(20) DEFAULT 'trial'
                CHECK (plan IN ('trial','starter','business','pro','enterprise')),
            trial_ends_at TIMESTAMPTZ,
            language VARCHAR(5) DEFAULT 'en',
            timezone VARCHAR(50) DEFAULT 'UTC',
            ai_tone VARCHAR(20) DEFAULT 'balanced'
                CHECK (ai_tone IN ('concise','balanced','detailed')),
            default_currency VARCHAR(3) DEFAULT 'EUR',
            telegram_chat_id BIGINT,
            telegram_link_code VARCHAR(20),
            telegram_username VARCHAR(100),
            is_superuser BOOLEAN DEFAULT false,
            force_password_change BOOLEAN DEFAULT false,
            is_active BOOLEAN DEFAULT true,
            avatar_url TEXT,
            last_login_at TIMESTAMPTZ,
            last_login_ip INET,
            login_count INTEGER DEFAULT 0,
            preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        );
        """
    )
    run("CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);")
    run("CREATE INDEX IF NOT EXISTS idx_users_plan ON users (plan);")
    run(
        "CREATE INDEX IF NOT EXISTS idx_users_telegram ON users (telegram_chat_id) "
        "WHERE telegram_chat_id IS NOT NULL;"
    )

    run(
        """
        CREATE TABLE IF NOT EXISTS user_subscriptions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            plan VARCHAR(20) NOT NULL
                CHECK (plan IN ('trial','starter','business','pro','enterprise')),
            status VARCHAR(20) DEFAULT 'active'
                CHECK (status IN ('active','cancelled','expired','past_due')),
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at TIMESTAMPTZ,
            cancelled_at TIMESTAMPTZ,
            payment_provider VARCHAR(30),
            external_id VARCHAR(255),
            amount_cents INTEGER,
            currency_code VARCHAR(3) DEFAULT 'EUR',
            created_at TIMESTAMPTZ DEFAULT now()
        );
        """
    )
    run("CREATE INDEX IF NOT EXISTS idx_user_subs_user ON user_subscriptions (user_id);")
    run("CREATE INDEX IF NOT EXISTS idx_user_subs_status ON user_subscriptions (status);")

    run(
        """
        CREATE TABLE IF NOT EXISTS user_products (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            product_id UUID NOT NULL REFERENCES dim_product(id) ON DELETE CASCADE,
            custom_name VARCHAR(500),
            custom_sku VARCHAR(100),
            target_price NUMERIC(12,2),
            cost_price NUMERIC(12,2),
            currency_code VARCHAR(3) DEFAULT 'EUR',
            notes TEXT,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now(),
            CONSTRAINT uq_user_products_user_product UNIQUE (user_id, product_id)
        );
        """
    )
    run("CREATE INDEX IF NOT EXISTS idx_user_products_user ON user_products (user_id);")
    run("CREATE INDEX IF NOT EXISTS idx_user_products_product ON user_products (product_id);")

    run(
        """
        CREATE TABLE IF NOT EXISTS fact_listing (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            product_id UUID NOT NULL REFERENCES dim_product(id) ON DELETE CASCADE,
            marketplace_id UUID NOT NULL REFERENCES dim_marketplace(id) ON DELETE CASCADE,
            seller_id UUID REFERENCES dim_seller(id) ON DELETE SET NULL,
            external_url TEXT NOT NULL,
            url_hash VARCHAR(64),
            external_id VARCHAR(200),
            external_name VARCHAR(500),
            last_price NUMERIC(12,2),
            last_price_eur NUMERIC(12,2),
            last_original_price NUMERIC(12,2),
            last_currency_code VARCHAR(3),
            last_in_stock BOOLEAN,
            last_rating NUMERIC(3,2),
            last_review_count INTEGER,
            last_checked_at TIMESTAMPTZ,
            scraper_type VARCHAR(30) DEFAULT 'web_api',
            scraper_config JSONB DEFAULT '{}',
            scrape_interval_minutes INTEGER DEFAULT 360,
            is_active BOOLEAN DEFAULT true,
            consecutive_errors INTEGER DEFAULT 0,
            last_error TEXT,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now(),
            CONSTRAINT uq_fact_listing_product_marketplace_seller_url
                UNIQUE (product_id, marketplace_id, seller_id, external_url)
        );
        """
    )
    run("CREATE INDEX IF NOT EXISTS idx_listing_product ON fact_listing (product_id);")
    run("CREATE INDEX IF NOT EXISTS idx_listing_marketplace ON fact_listing (marketplace_id);")
    run("CREATE INDEX IF NOT EXISTS idx_listing_seller ON fact_listing (seller_id);")
    run(
        "CREATE INDEX IF NOT EXISTS idx_listing_active ON fact_listing (is_active) WHERE is_active = true;"
    )
    run("CREATE INDEX IF NOT EXISTS idx_listing_last_checked ON fact_listing (last_checked_at);")
    run("CREATE UNIQUE INDEX IF NOT EXISTS idx_listing_url_hash ON fact_listing (url_hash);")

    run(
        """
        CREATE TABLE IF NOT EXISTS scrape_jobs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            job_type VARCHAR(30) NOT NULL
                CHECK (job_type IN ('scheduled','manual','retry','backfill','discovery','full_pipeline_test')),
            marketplace_id UUID REFERENCES dim_marketplace(id),
            status VARCHAR(20) DEFAULT 'pending'
                CHECK (status IN ('pending','running','completed','failed','cancelled')),
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            duration_ms INTEGER,
            total_listings INTEGER DEFAULT 0,
            successful INTEGER DEFAULT 0,
            failed INTEGER DEFAULT 0,
            skipped INTEGER DEFAULT 0,
            config JSONB DEFAULT '{}',
            triggered_by UUID REFERENCES users(id),
            created_at TIMESTAMPTZ DEFAULT now()
        );
        """
    )
    run("CREATE INDEX IF NOT EXISTS idx_scrape_jobs_status ON scrape_jobs (status);")
    run("CREATE INDEX IF NOT EXISTS idx_scrape_jobs_marketplace ON scrape_jobs (marketplace_id);")
    run("CREATE INDEX IF NOT EXISTS idx_scrape_jobs_created ON scrape_jobs (created_at);")

    run(
        """
        CREATE TABLE IF NOT EXISTS fact_price (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY,
            listing_id UUID NOT NULL REFERENCES fact_listing(id) ON DELETE CASCADE,
            date_id INTEGER NOT NULL REFERENCES dim_date(date_id),
            price NUMERIC(12,2) NOT NULL,
            original_price NUMERIC(12,2),
            currency_code VARCHAR(3) NOT NULL,
            price_eur NUMERIC(12,2),
            discount_pct NUMERIC(5,2),
            price_change_pct NUMERIC(8,4),
            in_stock BOOLEAN DEFAULT true,
            delivery_days SMALLINT,
            delivery_cost NUMERIC(8,2),
            seller_name VARCHAR(300),
            promo_label VARCHAR(300),
            is_promoted BOOLEAN DEFAULT false,
            promo_type VARCHAR(30),
            scraped_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            scrape_job_id UUID REFERENCES scrape_jobs(id),
            PRIMARY KEY (id, date_id)
        ) PARTITION BY RANGE (date_id);
        """
    )

    for suffix, frm, to in (
        ("202601", 20260101, 20260201),
        ("202602", 20260201, 20260301),
        ("202603", 20260301, 20260401),
        ("202604", 20260401, 20260501),
        ("202605", 20260501, 20260601),
        ("202606", 20260601, 20260701),
        ("202607", 20260701, 20260801),
        ("202608", 20260801, 20260901),
        ("202609", 20260901, 20261001),
        ("202610", 20261001, 20261101),
        ("202611", 20261101, 20261201),
        ("202612", 20261201, 20270101),
    ):
        run(
            f"""
            CREATE TABLE IF NOT EXISTS fact_price_{suffix} PARTITION OF fact_price
            FOR VALUES FROM ({frm}) TO ({to});
            """
        )

    run("CREATE INDEX IF NOT EXISTS idx_fact_price_listing ON fact_price (listing_id);")
    run("CREATE INDEX IF NOT EXISTS idx_fact_price_date ON fact_price (date_id);")
    run("CREATE INDEX IF NOT EXISTS idx_fact_price_scraped ON fact_price (scraped_at);")
    run(
        "CREATE INDEX IF NOT EXISTS idx_fact_price_listing_date ON fact_price (listing_id, date_id DESC);"
    )

    run(
        """
        CREATE TABLE IF NOT EXISTS fact_review (
            id BIGSERIAL PRIMARY KEY,
            listing_id UUID NOT NULL REFERENCES fact_listing(id) ON DELETE CASCADE,
            date_id INTEGER NOT NULL REFERENCES dim_date(date_id),
            rating_avg NUMERIC(3,2),
            review_count INTEGER NOT NULL DEFAULT 0,
            rating_1_count INTEGER DEFAULT 0,
            rating_2_count INTEGER DEFAULT 0,
            rating_3_count INTEGER DEFAULT 0,
            rating_4_count INTEGER DEFAULT 0,
            rating_5_count INTEGER DEFAULT 0,
            sentiment_score NUMERIC(4,3),
            sentiment_summary TEXT,
            new_reviews_24h INTEGER DEFAULT 0,
            scraped_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    run("CREATE INDEX IF NOT EXISTS idx_fact_review_listing ON fact_review (listing_id);")
    run("CREATE INDEX IF NOT EXISTS idx_fact_review_date ON fact_review (date_id);")
    run(
        "CREATE INDEX IF NOT EXISTS idx_fact_review_listing_date ON fact_review (listing_id, date_id DESC);"
    )

    run(
        """
        CREATE TABLE IF NOT EXISTS fact_stock (
            id BIGSERIAL PRIMARY KEY,
            listing_id UUID NOT NULL REFERENCES fact_listing(id) ON DELETE CASCADE,
            date_id INTEGER NOT NULL REFERENCES dim_date(date_id),
            in_stock BOOLEAN NOT NULL,
            stock_quantity INTEGER,
            stock_status VARCHAR(30),
            delivery_days_min SMALLINT,
            delivery_days_max SMALLINT,
            delivery_cost NUMERIC(8,2),
            delivery_type VARCHAR(30),
            scraped_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    run("CREATE INDEX IF NOT EXISTS idx_fact_stock_listing ON fact_stock (listing_id);")
    run("CREATE INDEX IF NOT EXISTS idx_fact_stock_date ON fact_stock (date_id);")
    run(
        "CREATE INDEX IF NOT EXISTS idx_fact_stock_oos ON fact_stock (listing_id, in_stock) "
        "WHERE in_stock = false;"
    )

    run(
        """
        CREATE TABLE IF NOT EXISTS fact_search_trend (
            id BIGSERIAL PRIMARY KEY,
            date_id INTEGER NOT NULL REFERENCES dim_date(date_id),
            country_code VARCHAR(2) NOT NULL REFERENCES dim_country(country_code),
            keyword VARCHAR(300) NOT NULL,
            keyword_normalized VARCHAR(300) NOT NULL,
            trend_index SMALLINT NOT NULL,
            search_volume INTEGER,
            source VARCHAR(30) NOT NULL
                CHECK (source IN (
                    'google_trends','kaspi_trends','amazon_trends',
                    'allegro_trends','custom'
                )),
            category_id UUID REFERENCES dim_category(id),
            related_product_id UUID REFERENCES dim_product(id),
            scraped_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    run(
        "CREATE INDEX IF NOT EXISTS idx_trend_keyword ON fact_search_trend "
        "USING gin (keyword_normalized gin_trgm_ops);"
    )
    run("CREATE INDEX IF NOT EXISTS idx_trend_date ON fact_search_trend (date_id);")
    run("CREATE INDEX IF NOT EXISTS idx_trend_country ON fact_search_trend (country_code);")
    run("CREATE INDEX IF NOT EXISTS idx_trend_source ON fact_search_trend (source);")

    run(
        """
        CREATE TABLE IF NOT EXISTS fact_currency_rate (
            id BIGSERIAL PRIMARY KEY,
            date_id INTEGER NOT NULL REFERENCES dim_date(date_id),
            currency_code VARCHAR(3) NOT NULL REFERENCES dim_currency(currency_code),
            rate_to_eur NUMERIC(18,8) NOT NULL,
            rate_to_usd NUMERIC(18,8) NOT NULL,
            source VARCHAR(30) NOT NULL
                CHECK (source IN (
                    'ecb','cbr','nbu','nbk','nbb','cbu','nbg','cba','cbar','openexchangerates','custom'
                )),
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (date_id, currency_code, source)
        );
        """
    )
    run("CREATE INDEX IF NOT EXISTS idx_rate_date ON fact_currency_rate (date_id);")
    run("CREATE INDEX IF NOT EXISTS idx_rate_currency ON fact_currency_rate (currency_code);")
    run(
        "CREATE INDEX IF NOT EXISTS idx_rate_date_currency ON fact_currency_rate (date_id, currency_code);"
    )

    run(
        """
        CREATE TABLE IF NOT EXISTS fact_tariff (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            hs_code VARCHAR(12) NOT NULL,
            origin_country VARCHAR(2) NOT NULL REFERENCES dim_country(country_code),
            destination_country VARCHAR(2) NOT NULL REFERENCES dim_country(country_code),
            duty_pct NUMERIC(6,3) NOT NULL,
            vat_pct NUMERIC(5,2),
            excise_pct NUMERIC(5,2),
            trade_agreement VARCHAR(100),
            effective_from DATE NOT NULL,
            effective_to DATE,
            source VARCHAR(100),
            source_url TEXT,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        );
        """
    )
    run("CREATE INDEX IF NOT EXISTS idx_tariff_hs ON fact_tariff (hs_code);")
    run(
        "CREATE INDEX IF NOT EXISTS idx_tariff_route ON fact_tariff (origin_country, destination_country);"
    )
    run("CREATE INDEX IF NOT EXISTS idx_tariff_effective ON fact_tariff (effective_from, effective_to);")

    run(
        """
        CREATE TABLE IF NOT EXISTS fact_promo (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            listing_id UUID REFERENCES fact_listing(id) ON DELETE SET NULL,
            marketplace_id UUID NOT NULL REFERENCES dim_marketplace(id),
            start_date_id INTEGER NOT NULL REFERENCES dim_date(date_id),
            end_date_id INTEGER REFERENCES dim_date(date_id),
            promo_type VARCHAR(30) NOT NULL
                CHECK (promo_type IN (
                    'flash_sale','seasonal','clearance','bundle','coupon','loyalty','marketplace_campaign',
                    'black_friday','singles_day','new_year','other'
                )),
            promo_name VARCHAR(300),
            discount_pct NUMERIC(5,2),
            discount_amount NUMERIC(12,2),
            currency_code VARCHAR(3),
            is_marketplace_wide BOOLEAN DEFAULT false,
            category_id UUID REFERENCES dim_category(id),
            detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_at TIMESTAMPTZ DEFAULT now()
        );
        """
    )
    run("CREATE INDEX IF NOT EXISTS idx_promo_marketplace ON fact_promo (marketplace_id);")
    run("CREATE INDEX IF NOT EXISTS idx_promo_listing ON fact_promo (listing_id);")
    run("CREATE INDEX IF NOT EXISTS idx_promo_dates ON fact_promo (start_date_id, end_date_id);")
    run("CREATE INDEX IF NOT EXISTS idx_promo_type ON fact_promo (promo_type);")

    run(
        """
        CREATE TABLE IF NOT EXISTS fact_crypto_price (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            date_id INTEGER NOT NULL REFERENCES dim_date(date_id),
            symbol VARCHAR(20) NOT NULL,
            name VARCHAR(100),
            price_usd NUMERIC(18,8) NOT NULL,
            price_eur NUMERIC(18,8),
            market_cap_usd NUMERIC(20,2),
            volume_24h_usd NUMERIC(20,2),
            change_1h_pct NUMERIC(8,4),
            change_24h_pct NUMERIC(8,4),
            change_7d_pct NUMERIC(8,4),
            high_24h_usd NUMERIC(18,8),
            low_24h_usd NUMERIC(18,8),
            circulating_supply NUMERIC(20,2),
            total_supply NUMERIC(20,2),
            source VARCHAR(30) NOT NULL
                CHECK (source IN ('binance','coingecko','coinmarketcap','custom')),
            rank SMALLINT,
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_crypto_date_symbol_source UNIQUE (date_id, symbol, source)
        );
        """
    )
    run("CREATE INDEX IF NOT EXISTS idx_crypto_date ON fact_crypto_price (date_id);")
    run("CREATE INDEX IF NOT EXISTS idx_crypto_symbol ON fact_crypto_price (symbol);")
    run("CREATE INDEX IF NOT EXISTS idx_crypto_date_symbol ON fact_crypto_price (date_id, symbol);")

    run(
        """
        CREATE TABLE IF NOT EXISTS fact_commodity_price (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            date_id INTEGER NOT NULL REFERENCES dim_date(date_id),
            symbol VARCHAR(20) NOT NULL,
            name VARCHAR(100) NOT NULL,
            commodity_type VARCHAR(20) NOT NULL
                CHECK (commodity_type IN ('metal','energy','agricultural')),
            price_usd NUMERIC(12,4) NOT NULL,
            price_eur NUMERIC(12,4),
            change_24h_pct NUMERIC(8,4),
            change_7d_pct NUMERIC(8,4),
            unit VARCHAR(20) NOT NULL,
            source VARCHAR(30) NOT NULL
                CHECK (source IN ('goldapi','alpha_vantage','eia','custom')),
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_commodity_date_symbol_source UNIQUE (date_id, symbol, source)
        );
        """
    )
    run("CREATE INDEX IF NOT EXISTS idx_commodity_date ON fact_commodity_price (date_id);")
    run("CREATE INDEX IF NOT EXISTS idx_commodity_symbol ON fact_commodity_price (symbol);")
    run(
        "CREATE INDEX IF NOT EXISTS idx_commodity_date_symbol ON fact_commodity_price (date_id, symbol);"
    )

    run(
        """
        CREATE TABLE IF NOT EXISTS fact_fuel_price (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            date_id INTEGER NOT NULL REFERENCES dim_date(date_id),
            country_code VARCHAR(2) NOT NULL REFERENCES dim_country(country_code),
            fuel_type VARCHAR(20) NOT NULL
                CHECK (fuel_type IN (
                    'gasoline_92','gasoline_95','gasoline_98','gasoline_100',
                    'diesel','diesel_premium','lpg','cng','electricity'
                )),
            price_local NUMERIC(8,4) NOT NULL,
            currency_code VARCHAR(3) NOT NULL REFERENCES dim_currency(currency_code),
            price_eur NUMERIC(8,4),
            change_week_pct NUMERIC(8,4),
            change_month_pct NUMERIC(8,4),
            source VARCHAR(50) NOT NULL,
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_fuel_date_country_type_source UNIQUE (date_id, country_code, fuel_type, source)
        );
        """
    )
    run("CREATE INDEX IF NOT EXISTS idx_fuel_date ON fact_fuel_price (date_id);")
    run("CREATE INDEX IF NOT EXISTS idx_fuel_country ON fact_fuel_price (country_code);")
    run(
        "CREATE INDEX IF NOT EXISTS idx_fuel_date_country_type ON fact_fuel_price "
        "(date_id, country_code, fuel_type);"
    )

    run(
        """
        CREATE TABLE IF NOT EXISTS alerts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            product_id UUID REFERENCES dim_product(id) ON DELETE SET NULL,
            listing_id UUID REFERENCES fact_listing(id) ON DELETE SET NULL,
            marketplace_id UUID REFERENCES dim_marketplace(id) ON DELETE SET NULL,
            category_id UUID REFERENCES dim_category(id) ON DELETE SET NULL,
            country_code VARCHAR(2) REFERENCES dim_country(country_code),
            alert_type VARCHAR(30) NOT NULL
                CHECK (alert_type IN (
                    'price_drop','price_increase','price_threshold',
                    'out_of_stock','back_in_stock',
                    'new_competitor','competitor_promo',
                    'review_drop','review_spike',
                    'trend_spike','trend_drop',
                    'currency_shift'
                )),
            threshold_pct NUMERIC(5,2),
            threshold_value NUMERIC(12,2),
            channel VARCHAR(20) DEFAULT 'email'
                CHECK (channel IN ('email','telegram','push','webhook','all')),
            webhook_url TEXT,
            cooldown_minutes INTEGER DEFAULT 60,
            last_triggered_at TIMESTAMPTZ,
            trigger_count INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        );
        """
    )
    run("CREATE INDEX IF NOT EXISTS idx_alerts_user ON alerts (user_id);")
    run("CREATE INDEX IF NOT EXISTS idx_alerts_active ON alerts (is_active) WHERE is_active = true;")
    run("CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts (alert_type);")

    run(
        """
        CREATE TABLE IF NOT EXISTS alert_events (
            id BIGSERIAL PRIMARY KEY,
            alert_id UUID NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
            listing_id UUID REFERENCES fact_listing(id) ON DELETE SET NULL,
            fact_price_id BIGINT,
            old_value NUMERIC(12,2),
            new_value NUMERIC(12,2),
            change_pct NUMERIC(8,4),
            message TEXT NOT NULL,
            severity VARCHAR(10) DEFAULT 'medium'
                CHECK (severity IN ('low','medium','high','critical')),
            ai_explanation TEXT,
            ai_recommendation TEXT,
            ai_recommended_price NUMERIC(12,2),
            ai_confidence NUMERIC(3,2),
            sent_via VARCHAR(20),
            delivered_at TIMESTAMPTZ,
            read_at TIMESTAMPTZ,
            triggered_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    run("CREATE INDEX IF NOT EXISTS idx_alert_events_alert ON alert_events (alert_id);")
    run("CREATE INDEX IF NOT EXISTS idx_alert_events_triggered ON alert_events (triggered_at);")
    run("CREATE INDEX IF NOT EXISTS idx_alert_events_severity ON alert_events (severity);")

    run(
        """
        CREATE TABLE IF NOT EXISTS digests (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            period_type VARCHAR(10) NOT NULL
                CHECK (period_type IN ('daily','weekly','monthly','custom')),
            digest_type VARCHAR(30) DEFAULT 'market_overview'
                CHECK (digest_type IN (
                    'market_overview','price_changes','competitor_analysis','trend_report',
                    'anomaly_digest','custom'
                )),
            period_start TIMESTAMPTZ NOT NULL,
            period_end TIMESTAMPTZ NOT NULL,
            title VARCHAR(300),
            content_md TEXT,
            summary_json JSONB,
            product_ids UUID[] DEFAULT '{}',
            marketplace_ids UUID[] DEFAULT '{}',
            country_codes VARCHAR(2)[] DEFAULT '{}',
            sent_at TIMESTAMPTZ,
            sent_via VARCHAR(20),
            tokens_used INTEGER,
            model_used VARCHAR(50),
            generation_ms INTEGER,
            created_at TIMESTAMPTZ DEFAULT now()
        );
        """
    )
    run("CREATE INDEX IF NOT EXISTS idx_digests_user ON digests (user_id);")
    run("CREATE INDEX IF NOT EXISTS idx_digests_period ON digests (period_start, period_end);")
    run("CREATE INDEX IF NOT EXISTS idx_digests_type ON digests (digest_type);")

    run(
        """
        CREATE TABLE IF NOT EXISTS ai_chat_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title VARCHAR(300),
            context_type VARCHAR(30) DEFAULT 'general'
                CHECK (context_type IN (
                    'general','product','marketplace','category','competitor','digest','alert'
                )),
            context_id UUID,
            message_count INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            is_archived BOOLEAN DEFAULT false,
            last_message_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        );
        """
    )
    run("CREATE INDEX IF NOT EXISTS idx_chat_sessions_user ON ai_chat_sessions (user_id);")
    run(
        "CREATE INDEX IF NOT EXISTS idx_chat_sessions_context ON ai_chat_sessions (context_type, context_id);"
    )

    run(
        """
        CREATE TABLE IF NOT EXISTS ai_chat_messages (
            id BIGSERIAL PRIMARY KEY,
            session_id UUID NOT NULL REFERENCES ai_chat_sessions(id) ON DELETE CASCADE,
            role VARCHAR(10) NOT NULL
                CHECK (role IN ('user','assistant','system','tool')),
            content TEXT NOT NULL,
            tokens_used INTEGER,
            model_used VARCHAR(50),
            duration_ms INTEGER,
            tool_calls JSONB,
            user_rating SMALLINT
                CHECK (user_rating IS NULL OR (user_rating BETWEEN 1 AND 5)),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    run("CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON ai_chat_messages (session_id);")
    run("CREATE INDEX IF NOT EXISTS idx_chat_messages_created ON ai_chat_messages (created_at);")

    run(
        """
        CREATE TABLE IF NOT EXISTS scrape_logs (
            id BIGSERIAL PRIMARY KEY,
            scrape_job_id UUID REFERENCES scrape_jobs(id) ON DELETE SET NULL,
            listing_id UUID NOT NULL REFERENCES fact_listing(id) ON DELETE CASCADE,
            marketplace_id UUID NOT NULL REFERENCES dim_marketplace(id),
            status VARCHAR(50) NOT NULL
                CHECK (status IN (
                    'success','error','timeout','blocked','captcha',
                    'not_found','price_not_found','parse_error','missing_critical_data',
                    'technical_error'
                )),
            url TEXT NOT NULL,
            price_found NUMERIC(12,2),
            in_stock_found BOOLEAN,
            duration_ms INTEGER,
            response_code SMALLINT,
            proxy_used VARCHAR(100),
            scraper_type VARCHAR(30),
            error_message TEXT,
            error_category VARCHAR(30),
            retry_count SMALLINT DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    run("CREATE INDEX IF NOT EXISTS idx_scrape_logs_job ON scrape_logs (scrape_job_id);")
    run("CREATE INDEX IF NOT EXISTS idx_scrape_logs_listing ON scrape_logs (listing_id);")
    run("CREATE INDEX IF NOT EXISTS idx_scrape_logs_status ON scrape_logs (status);")
    run("CREATE INDEX IF NOT EXISTS idx_scrape_logs_created ON scrape_logs (created_at);")

    run(
        """
        CREATE TABLE IF NOT EXISTS api_logs (
            id BIGSERIAL PRIMARY KEY,
            service VARCHAR(50) NOT NULL,
            endpoint VARCHAR(500),
            method VARCHAR(10) DEFAULT 'GET',
            status VARCHAR(20) NOT NULL
                CHECK (status IN ('success','error','timeout','rate_limited')),
            status_code SMALLINT,
            duration_ms INTEGER,
            tokens_used INTEGER,
            request_size_bytes INTEGER,
            response_size_bytes INTEGER,
            error_message TEXT,
            user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    run("CREATE INDEX IF NOT EXISTS idx_api_logs_service ON api_logs (service);")
    run("CREATE INDEX IF NOT EXISTS idx_api_logs_status ON api_logs (status);")
    run("CREATE INDEX IF NOT EXISTS idx_api_logs_created ON api_logs (created_at);")
    run("CREATE INDEX IF NOT EXISTS idx_api_logs_user ON api_logs (user_id) WHERE user_id IS NOT NULL;")

    run(
        """
        CREATE TABLE IF NOT EXISTS data_exports (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            export_type VARCHAR(30) NOT NULL
                CHECK (export_type IN (
                    'csv','xlsx','json','parquet','pdf_report','powerbi_dataset','api_bulk'
                )),
            tables_included VARCHAR(50)[] NOT NULL,
            filters JSONB DEFAULT '{}',
            row_count INTEGER,
            file_size_bytes BIGINT,
            file_url TEXT,
            expires_at TIMESTAMPTZ,
            status VARCHAR(20) DEFAULT 'pending'
                CHECK (status IN ('pending','generating','ready','downloaded','expired','error')),
            created_at TIMESTAMPTZ DEFAULT now(),
            completed_at TIMESTAMPTZ
        );
        """
    )
    run("CREATE INDEX IF NOT EXISTS idx_exports_user ON data_exports (user_id);")
    run("CREATE INDEX IF NOT EXISTS idx_exports_status ON data_exports (status);")

    # --- Drift repair: columns from 002 on older DBs that only ran partial migrations ---
    _repair_drift_columns(run)

    # --- Seeds (idempotent) ---
    run(
        """
        INSERT INTO dim_date (
            date_id, full_date, year, quarter, month, month_name, week_iso,
            day_of_month, day_of_week, day_name, is_weekend, is_last_day_of_month
        )
        SELECT
            TO_CHAR(d, 'YYYYMMDD')::INTEGER,
            d,
            EXTRACT(YEAR FROM d)::SMALLINT,
            EXTRACT(QUARTER FROM d)::SMALLINT,
            EXTRACT(MONTH FROM d)::SMALLINT,
            TRIM(TO_CHAR(d, 'Month')),
            EXTRACT(WEEK FROM d)::SMALLINT,
            EXTRACT(DAY FROM d)::SMALLINT,
            EXTRACT(ISODOW FROM d)::SMALLINT,
            TRIM(TO_CHAR(d, 'Day')),
            EXTRACT(ISODOW FROM d) IN (6, 7),
            d = (DATE_TRUNC('month', d) + INTERVAL '1 month' - INTERVAL '1 day')::DATE
        FROM generate_series('2024-01-01'::DATE, '2030-12-31'::DATE, '1 day') AS d
        ON CONFLICT (date_id) DO NOTHING;
        """
    )
    run("UPDATE dim_date SET week_iso = EXTRACT(WEEK FROM full_date)::SMALLINT;")

    run(
        """
        INSERT INTO dim_currency (currency_code, name, symbol, decimal_places) VALUES
        ('EUR', 'Euro', '€', 2), ('USD', 'US Dollar', '$', 2),
        ('RUB', 'Russian Ruble', '₽', 2), ('UAH', 'Ukrainian Hryvnia', '₴', 2),
        ('KZT', 'Kazakh Tenge', '₸', 2), ('BYN', 'Belarusian Ruble', 'Br', 2),
        ('UZS', 'Uzbek Sum', 'сўм', 2), ('GEL', 'Georgian Lari', '₾', 2),
        ('AMD', 'Armenian Dram', '֏', 2), ('AZN', 'Azerbaijani Manat', '₼', 2),
        ('KGS', 'Kyrgyz Som', 'сом', 2), ('TJS', 'Tajik Somoni', 'SM', 2),
        ('MDL', 'Moldovan Leu', 'L', 2), ('PLN', 'Polish Zloty', 'zł', 2),
        ('CZK', 'Czech Koruna', 'Kč', 2), ('HUF', 'Hungarian Forint', 'Ft', 0),
        ('RON', 'Romanian Leu', 'lei', 2), ('BGN', 'Bulgarian Lev', 'лв', 2),
        ('HRK', 'Croatian Kuna', 'kn', 2), ('RSD', 'Serbian Dinar', 'din', 2),
        ('TRY', 'Turkish Lira', '₺', 2), ('GBP', 'British Pound', '£', 2),
        ('CHF', 'Swiss Franc', 'CHF', 2), ('SEK', 'Swedish Krona', 'kr', 2),
        ('NOK', 'Norwegian Krone', 'kr', 2), ('DKK', 'Danish Krone', 'kr', 2),
        ('ISK', 'Icelandic Krona', 'kr', 0),
        ('BAM', 'Bosnia and Herzegovina Convertible Mark', 'KM', 2),
        ('MKD', 'Macedonian Denar', 'ден', 2),
        ('ALL', 'Albanian Lek', 'L', 2)
        ON CONFLICT (currency_code) DO NOTHING;
        """
    )

    run(
        """
        INSERT INTO dim_country (
            country_code, name, name_local, region, currency_code, vat_rate_std
        ) VALUES
        ('RU', 'Russia', 'Россия', 'CIS', 'RUB', 20.00),
        ('KZ', 'Kazakhstan', 'Қазақстан', 'CIS', 'KZT', 12.00),
        ('UA', 'Ukraine', 'Україна', 'CIS', 'UAH', 20.00),
        ('BY', 'Belarus', 'Беларусь', 'CIS', 'BYN', 20.00),
        ('UZ', 'Uzbekistan', 'Oʻzbekiston', 'Central_Asia', 'UZS', 12.00),
        ('MD', 'Moldova', 'Moldova', 'CIS', 'MDL', 20.00),
        ('GE', 'Georgia', 'საქართველო', 'Caucasus', 'GEL', 18.00),
        ('AM', 'Armenia', 'Հայաստան', 'Caucasus', 'AMD', 20.00),
        ('AZ', 'Azerbaijan', 'Azərbaycan', 'Caucasus', 'AZN', 18.00),
        ('KG', 'Kyrgyzstan', 'Кыргызстан', 'Central_Asia', 'KGS', 12.00),
        ('TJ', 'Tajikistan', 'Тоҷикистон', 'Central_Asia', 'TJS', 15.00),
        ('DE', 'Germany', 'Deutschland', 'EU', 'EUR', 19.00),
        ('PL', 'Poland', 'Polska', 'EU', 'PLN', 23.00),
        ('FR', 'France', 'France', 'EU', 'EUR', 20.00),
        ('NL', 'Netherlands', 'Nederland', 'EU', 'EUR', 21.00),
        ('CZ', 'Czech Republic', 'Česko', 'EU', 'CZK', 21.00),
        ('SK', 'Slovakia', 'Slovensko', 'EU', 'EUR', 20.00),
        ('AT', 'Austria', 'Österreich', 'EU', 'EUR', 20.00),
        ('LV', 'Latvia', 'Latvija', 'EU', 'EUR', 21.00),
        ('LT', 'Lithuania', 'Lietuva', 'EU', 'EUR', 21.00),
        ('EE', 'Estonia', 'Eesti', 'EU', 'EUR', 22.00),
        ('RO', 'Romania', 'România', 'EU', 'RON', 19.00),
        ('HU', 'Hungary', 'Magyarország', 'EU', 'HUF', 27.00),
        ('BG', 'Bulgaria', 'България', 'EU', 'BGN', 20.00),
        ('HR', 'Croatia', 'Hrvatska', 'EU', 'EUR', 25.00),
        ('SI', 'Slovenia', 'Slovenija', 'EU', 'EUR', 22.00),
        ('GR', 'Greece', 'Ελλάδα', 'EU', 'EUR', 24.00),
        ('IT', 'Italy', 'Italia', 'EU', 'EUR', 22.00),
        ('ES', 'Spain', 'España', 'EU', 'EUR', 21.00),
        ('PT', 'Portugal', 'Portugal', 'EU', 'EUR', 23.00),
        ('RS', 'Serbia', 'Србија', 'Balkans', 'RSD', 20.00),
        ('BA', 'Bosnia and Herzegovina', 'Bosna i Hercegovina', 'Balkans', 'BAM', 17.00),
        ('MK', 'North Macedonia', 'Северна Македонија', 'Balkans', 'MKD', 18.00),
        ('ME', 'Montenegro', 'Crna Gora', 'Balkans', 'EUR', 21.00),
        ('AL', 'Albania', 'Shqipëria', 'Balkans', 'ALL', 20.00),
        ('TR', 'Turkey', 'Türkiye', 'Turkey', 'TRY', 20.00),
        ('FI', 'Finland', 'Suomi', 'EU', 'EUR', 25.50),
        ('SE', 'Sweden', 'Sverige', 'EU', 'SEK', 25.00),
        ('DK', 'Denmark', 'Danmark', 'EU', 'DKK', 25.00),
        ('NO', 'Norway', 'Norge', 'EFTA', 'NOK', 25.00),
        ('UK', 'United Kingdom', 'United Kingdom', 'Other', 'GBP', 20.00),
        ('CH', 'Switzerland', 'Schweiz', 'EFTA', 'CHF', 8.10),
        ('BE', 'Belgium', 'België', 'EU', 'EUR', 21.00),
        ('IE', 'Ireland', 'Éire', 'EU', 'EUR', 23.00)
        ON CONFLICT (country_code) DO NOTHING;
        """
    )

    # --- Materialized views ---
    run(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_price_summary AS
        SELECT
            fp.date_id,
            fl.product_id,
            fl.marketplace_id,
            dp.category_id,
            dp.brand_id,
            dm.country_code,
            COUNT(DISTINCT fl.id) AS listing_count,
            MIN(fp.price_eur) AS min_price_eur,
            MAX(fp.price_eur) AS max_price_eur,
            AVG(fp.price_eur)::NUMERIC(12,2) AS avg_price_eur,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY fp.price_eur) AS median_price_eur,
            COUNT(*) FILTER (WHERE fp.in_stock = true) AS in_stock_count,
            COUNT(*) FILTER (WHERE fp.in_stock = false) AS out_of_stock_count,
            COUNT(*) FILTER (WHERE fp.is_promoted = true) AS promoted_count,
            AVG(fp.discount_pct) FILTER (WHERE fp.discount_pct > 0) AS avg_discount_pct
        FROM fact_price fp
        JOIN fact_listing fl ON fp.listing_id = fl.id
        JOIN dim_product dp ON fl.product_id = dp.id
        JOIN dim_marketplace dm ON fl.marketplace_id = dm.id
        GROUP BY fp.date_id, fl.product_id, fl.marketplace_id, dp.category_id, dp.brand_id, dm.country_code
        WITH NO DATA;
        """
    )

    run(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_marketplace_health AS
        SELECT
            dm.id AS marketplace_id,
            dm.marketplace_code,
            dm.name,
            dm.country_code,
            COUNT(DISTINCT fl.id) AS active_listings,
            COUNT(DISTINCT sl.id) FILTER (WHERE sl.created_at > now() - interval '24 hours') AS scrapes_24h,
            COUNT(DISTINCT sl.id) FILTER (WHERE sl.status = 'success' AND sl.created_at > now() - interval '24 hours') AS success_24h,
            COUNT(DISTINCT sl.id) FILTER (WHERE sl.status = 'error' AND sl.created_at > now() - interval '24 hours') AS errors_24h,
            CASE
                WHEN COUNT(DISTINCT sl.id) FILTER (WHERE sl.created_at > now() - interval '24 hours') = 0 THEN 0::NUMERIC
                ELSE (
                    COUNT(DISTINCT sl.id) FILTER (WHERE sl.status = 'success' AND sl.created_at > now() - interval '24 hours')::NUMERIC
                    / NULLIF(COUNT(DISTINCT sl.id) FILTER (WHERE sl.created_at > now() - interval '24 hours'), 0)
                )
            END AS success_rate_24h,
            AVG(sl.duration_ms) FILTER (WHERE sl.created_at > now() - interval '24 hours') AS avg_duration_ms_24h
        FROM dim_marketplace dm
        LEFT JOIN fact_listing fl ON dm.id = fl.marketplace_id AND fl.is_active = true
        LEFT JOIN scrape_logs sl ON dm.id = sl.marketplace_id
        GROUP BY dm.id, dm.marketplace_code, dm.name, dm.country_code
        WITH NO DATA;
        """
    )

    run(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_daily_price ON mv_daily_price_summary
            (date_id, product_id, marketplace_id);
        CREATE INDEX IF NOT EXISTS idx_mv_daily_price_date ON mv_daily_price_summary (date_id);
        CREATE INDEX IF NOT EXISTS idx_mv_daily_price_product ON mv_daily_price_summary (product_id);
        CREATE INDEX IF NOT EXISTS idx_mv_daily_price_category ON mv_daily_price_summary (category_id);
        """
    )

    run(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_marketplace_health ON mv_marketplace_health (marketplace_id);
        """
    )

    _repair_scrape_logs_constraint(run)
    _repair_scrape_job_types_constraint(run)


def _repair_drift_columns(run: Callable[[str], None]) -> None:
    """Add columns introduced in 002+ when tables pre-existed without them."""
    run(
        """
        ALTER TABLE dim_marketplace ADD COLUMN IF NOT EXISTS product_quota INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE dim_marketplace ADD COLUMN IF NOT EXISTS products_in_pool INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE dim_marketplace ADD COLUMN IF NOT EXISTS requires_js BOOLEAN NOT NULL DEFAULT false;
        ALTER TABLE dim_marketplace ADD COLUMN IF NOT EXISTS rate_limit_delay NUMERIC(4,1) NOT NULL DEFAULT 2.0;
        ALTER TABLE dim_marketplace ADD COLUMN IF NOT EXISTS custom_product_link_selector TEXT;
        ALTER TABLE dim_marketplace ADD COLUMN IF NOT EXISTS custom_next_page_selector TEXT;
        ALTER TABLE dim_marketplace ADD COLUMN IF NOT EXISTS custom_price_selector TEXT;
        ALTER TABLE dim_marketplace ADD COLUMN IF NOT EXISTS custom_title_selector TEXT;
        ALTER TABLE dim_marketplace ADD COLUMN IF NOT EXISTS last_discovery_at TIMESTAMPTZ;
        ALTER TABLE dim_marketplace ADD COLUMN IF NOT EXISTS last_discovery_status VARCHAR(20);
        ALTER TABLE dim_marketplace ADD COLUMN IF NOT EXISTS last_discovery_products_found INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE dim_marketplace ADD COLUMN IF NOT EXISTS discovery_error_count INTEGER NOT NULL DEFAULT 0;
        """
    )
    run("ALTER TABLE fact_listing ADD COLUMN IF NOT EXISTS url_hash VARCHAR(64);")
    run(
        """
        ALTER TABLE users ADD COLUMN IF NOT EXISTS timezone VARCHAR(50) DEFAULT 'UTC';
        ALTER TABLE users ADD COLUMN IF NOT EXISTS default_currency VARCHAR(3) DEFAULT 'EUR';
        ALTER TABLE users ADD COLUMN IF NOT EXISTS telegram_username VARCHAR(100);
        ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_ip INET;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS login_count INTEGER DEFAULT 0;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS preferences JSONB NOT NULL DEFAULT '{}'::jsonb;
        """
    )


def _repair_scrape_logs_constraint(run: Callable[[str], None]) -> None:
    """Align scrape_logs status CHECK with migrations 005–006 when table pre-dates them."""
    run(
        """
        DO $body$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'scrape_logs'
          ) THEN
            ALTER TABLE public.scrape_logs DROP CONSTRAINT IF EXISTS ck_scrape_logs_status;
            ALTER TABLE public.scrape_logs ADD CONSTRAINT ck_scrape_logs_status CHECK (
              status IN (
                'success','error','timeout','blocked','captcha',
                'not_found','price_not_found','parse_error','missing_critical_data',
                'technical_error'
              )
            );
          END IF;
        END
        $body$ LANGUAGE plpgsql;
        """
    )
    run(
        """
        DO $body$
        DECLARE
          clen integer;
          dt text;
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'scrape_logs'
          ) THEN
            RETURN;
          END IF;
          SELECT c.data_type, c.character_maximum_length INTO dt, clen
          FROM information_schema.columns c
          WHERE c.table_schema = 'public'
            AND c.table_name = 'scrape_logs'
            AND c.column_name = 'status';
          IF NOT FOUND THEN
            RETURN;
          END IF;
          IF dt = 'text' OR (clen IS NOT NULL AND clen >= 50) THEN
            RETURN;
          END IF;
          ALTER TABLE public.scrape_logs ALTER COLUMN status TYPE VARCHAR(50);
        END
        $body$ LANGUAGE plpgsql;
        """
    )


def _repair_scrape_job_types_constraint(run: Callable[[str], None]) -> None:
    """Align scrape_jobs job_type CHECK with full-pipeline admin task."""
    run(
        """
        DO $body$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'scrape_jobs'
          ) THEN
            ALTER TABLE public.scrape_jobs DROP CONSTRAINT IF EXISTS ck_scrape_jobs_job_type;
            ALTER TABLE public.scrape_jobs ADD CONSTRAINT ck_scrape_jobs_job_type CHECK (
              job_type IN (
                'scheduled','manual','retry','backfill','discovery','full_pipeline_test'
              )
            );
          END IF;
        END
        $body$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    """Downgrade not supported: v2 rebuild migration is append-only."""
    raise NotImplementedError("009_full_v2_schema_rebuild downgrade is not supported")
