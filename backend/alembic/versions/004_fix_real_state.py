"""Fix real DB state: ALTER users to v2, drop legacy tables."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "004_fix_real_state"
down_revision = "003_fix_users_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============================================================
    # PART 1: Fix users table — convert ENUM plan to VARCHAR,
    #         add missing v2 columns
    # ============================================================

    # Convert plan from ENUM to VARCHAR
    op.execute(sa.text("ALTER TABLE users ALTER COLUMN plan TYPE VARCHAR(20) USING plan::text"))

    # Add CHECK constraint matching v2 schema
    op.execute(
        sa.text(
            "ALTER TABLE users ADD CONSTRAINT ck_users_plan "
            "CHECK (plan IN ('trial','starter','business','pro','enterprise'))"
        )
    )

    # Drop old ENUM type if exists
    op.execute(sa.text("DROP TYPE IF EXISTS userplan"))

    # Add missing columns (IF NOT EXISTS prevents errors on re-run)
    op.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS timezone VARCHAR(50) DEFAULT 'UTC'"))
    op.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS default_currency VARCHAR(3) DEFAULT 'EUR'"))
    op.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS telegram_username VARCHAR(100)"))
    op.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true"))
    op.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_ip INET"))
    op.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS login_count INTEGER DEFAULT 0"))
    op.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS preferences JSONB DEFAULT '{}'"))

    # Make name nullable (v2 allows NULL)
    op.execute(sa.text("ALTER TABLE users ALTER COLUMN name DROP NOT NULL"))

    # ============================================================
    # PART 2: Drop ALL legacy tables (order: FK children first)
    # ============================================================

    # Drop tables that reference other old tables (FK children)
    op.execute(sa.text("DROP TABLE IF EXISTS price_snapshots CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS alert_events CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS scrape_logs CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS discovery_logs CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS global_price_snapshots CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS competitor_products CASCADE"))

    # Drop tables that are referenced (FK parents)
    op.execute(sa.text("DROP TABLE IF EXISTS global_products CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS competitors CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS products CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS admin_marketplaces CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS alerts CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS digests CASCADE"))

    # Drop old markets_* tables
    op.execute(sa.text("DROP TABLE IF EXISTS markets_forex CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS markets_crypto CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS markets_commodities CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS markets_ticker CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS markets_overview CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS markets_preferences CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS markets_refresh_log CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS markets_category_analytics CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS markets_marketplace_analytics CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS markets_opportunities CASCADE"))

    # Drop old AI chat tables (v2 has new ones created by 001)
    op.execute(sa.text("DROP TABLE IF EXISTS ai_chat_messages CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS ai_chat_sessions CASCADE"))

    # Drop old alembic_version in public (we use alembic_meta now)
    op.execute(sa.text("DROP TABLE IF EXISTS public.alembic_version CASCADE"))

    # Drop old ENUM types
    op.execute(sa.text("DROP TYPE IF EXISTS userplan"))
    op.execute(sa.text("DROP TYPE IF EXISTS refreshtype"))
    op.execute(sa.text("DROP TYPE IF EXISTS refreshstatus"))

    # Drop old sequences that may remain
    op.execute(sa.text("DROP SEQUENCE IF EXISTS admin_marketplaces_id_seq CASCADE"))
    op.execute(sa.text("DROP SEQUENCE IF EXISTS discovery_logs_id_seq CASCADE"))
    op.execute(sa.text("DROP SEQUENCE IF EXISTS global_products_id_seq CASCADE"))
    op.execute(sa.text("DROP SEQUENCE IF EXISTS global_price_snapshots_id_seq CASCADE"))
    op.execute(sa.text("DROP SEQUENCE IF EXISTS markets_forex_id_seq CASCADE"))
    op.execute(sa.text("DROP SEQUENCE IF EXISTS markets_crypto_id_seq CASCADE"))
    op.execute(sa.text("DROP SEQUENCE IF EXISTS markets_commodities_id_seq CASCADE"))
    op.execute(sa.text("DROP SEQUENCE IF EXISTS markets_ticker_id_seq CASCADE"))
    op.execute(sa.text("DROP SEQUENCE IF EXISTS markets_refresh_log_id_seq CASCADE"))
    op.execute(sa.text("DROP SEQUENCE IF EXISTS price_snapshots_id_seq CASCADE"))

    # ============================================================
    # PART 3: Recreate app tables that had old structure
    #         (001 couldn't replace them because DROP SCHEMA failed)
    # ============================================================

    # alerts (v2) — only create if not exists (001 may have created it)
    op.execute(
        sa.text(
            """
        CREATE TABLE IF NOT EXISTS alerts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            product_id UUID REFERENCES dim_product(id) ON DELETE SET NULL,
            listing_id UUID REFERENCES fact_listing(id) ON DELETE SET NULL,
            marketplace_id UUID REFERENCES dim_marketplace(id) ON DELETE SET NULL,
            category_id UUID REFERENCES dim_category(id) ON DELETE SET NULL,
            country_code VARCHAR(2) REFERENCES dim_country(country_code),
            alert_type VARCHAR(30) NOT NULL,
            threshold_pct NUMERIC(5,2),
            threshold_value NUMERIC(12,2),
            channel VARCHAR(20) DEFAULT 'email',
            webhook_url TEXT,
            cooldown_minutes INTEGER DEFAULT 60,
            last_triggered_at TIMESTAMPTZ,
            trigger_count INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        )
    """
        )
    )

    # alert_events (v2)
    op.execute(
        sa.text(
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
            severity VARCHAR(10) DEFAULT 'medium',
            ai_explanation TEXT,
            ai_recommendation TEXT,
            ai_recommended_price NUMERIC(12,2),
            ai_confidence NUMERIC(3,2),
            sent_via VARCHAR(20),
            delivered_at TIMESTAMPTZ,
            read_at TIMESTAMPTZ,
            triggered_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """
        )
    )

    # digests (v2)
    op.execute(
        sa.text(
            """
        CREATE TABLE IF NOT EXISTS digests (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            period_type VARCHAR(10) NOT NULL,
            digest_type VARCHAR(30) DEFAULT 'market_overview',
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
        )
    """
        )
    )

    # ai_chat_sessions (v2 — UUID PK)
    op.execute(
        sa.text(
            """
        CREATE TABLE IF NOT EXISTS ai_chat_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title VARCHAR(300),
            context_type VARCHAR(30) DEFAULT 'general',
            context_id UUID,
            message_count INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            is_archived BOOLEAN DEFAULT false,
            last_message_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        )
    """
        )
    )

    # ai_chat_messages (v2 — UUID FK)
    op.execute(
        sa.text(
            """
        CREATE TABLE IF NOT EXISTS ai_chat_messages (
            id BIGSERIAL PRIMARY KEY,
            session_id UUID NOT NULL REFERENCES ai_chat_sessions(id) ON DELETE CASCADE,
            role VARCHAR(10) NOT NULL,
            content TEXT NOT NULL,
            tokens_used INTEGER,
            model_used VARCHAR(50),
            duration_ms INTEGER,
            tool_calls JSONB,
            user_rating SMALLINT CHECK (user_rating BETWEEN 1 AND 5),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """
        )
    )

    # ============================================================
    # PART 4: Ensure pg_trgm extension
    # ============================================================
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))


def downgrade() -> None:
    pass
