"""Add missing monthly partitions for 2026 (Jun-Dec) and a DEFAULT safety partition.

Revision ID: 015_fact_price_default_partition
Revises: 014_marketplace_scrape_tier
Create Date: 2026-06-03

Rationale: migration 009 created RANGE-partitioned fact_price table but only
created monthly partitions up to a limited range. On 2026-06-02 every INSERT
started failing with 'no partition of relation fact_price found for row'.
This migration adds remaining monthly partitions for 2026 and installs a
DEFAULT partition as a safety net so future gaps cannot block writes again.

The DEFAULT partition is not a permanent home — administrators are expected
to create explicit monthly partitions ahead of time and move any rows from
DEFAULT into them. Until automated partition maintenance exists, DEFAULT
guards against silent data loss.
"""

from alembic import op

revision = "015_fact_price_default_partition"
down_revision = "014_marketplace_scrape_tier"
branch_labels = None
depends_on = None


def _exec(sql: str) -> None:
    op.execute(sql)


def upgrade() -> None:
    # Monthly partitions for the remainder of 2026.
    # Idempotent: IF NOT EXISTS guards against re-running on databases where
    # admins already created partitions manually (FIX-A operational step).
    _exec(
        "CREATE TABLE IF NOT EXISTS fact_price_202606 "
        "PARTITION OF fact_price FOR VALUES FROM (20260601) TO (20260701)"
    )
    _exec(
        "CREATE TABLE IF NOT EXISTS fact_price_202607 "
        "PARTITION OF fact_price FOR VALUES FROM (20260701) TO (20260801)"
    )
    _exec(
        "CREATE TABLE IF NOT EXISTS fact_price_202608 "
        "PARTITION OF fact_price FOR VALUES FROM (20260801) TO (20260901)"
    )
    _exec(
        "CREATE TABLE IF NOT EXISTS fact_price_202609 "
        "PARTITION OF fact_price FOR VALUES FROM (20260901) TO (20261001)"
    )
    _exec(
        "CREATE TABLE IF NOT EXISTS fact_price_202610 "
        "PARTITION OF fact_price FOR VALUES FROM (20261001) TO (20261101)"
    )
    _exec(
        "CREATE TABLE IF NOT EXISTS fact_price_202611 "
        "PARTITION OF fact_price FOR VALUES FROM (20261101) TO (20261201)"
    )
    _exec(
        "CREATE TABLE IF NOT EXISTS fact_price_202612 "
        "PARTITION OF fact_price FOR VALUES FROM (20261201) TO (20270101)"
    )
    # DEFAULT partition as safety net.
    _exec(
        "CREATE TABLE IF NOT EXISTS fact_price_default "
        "PARTITION OF fact_price DEFAULT"
    )


def downgrade() -> None:
    # Order matters: DEFAULT before monthly partitions, otherwise data in
    # DEFAULT cannot be re-routed.
    _exec("DROP TABLE IF EXISTS fact_price_default")
    _exec("DROP TABLE IF EXISTS fact_price_202612")
    _exec("DROP TABLE IF EXISTS fact_price_202611")
    _exec("DROP TABLE IF EXISTS fact_price_202610")
    _exec("DROP TABLE IF EXISTS fact_price_202609")
    _exec("DROP TABLE IF EXISTS fact_price_202608")
    _exec("DROP TABLE IF EXISTS fact_price_202607")
    _exec("DROP TABLE IF EXISTS fact_price_202606")
