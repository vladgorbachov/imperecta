"""Stale-selection indexes for adaptive per-listing refresh.

Revision ID: 052_stale_due_index
Revises: 051_pool_read_perf
Create Date: 2026-09-18

The worker's stale query (scraper/tasks.py) has two branches:

  1. last_checked_at IS NULL — never-scraped skeletons; the bulk of the
     1.4M pool after sitemap onboarding. Served by a partial index keyed
     by marketplace_id (the per-marketplace pipeline filter joins on it).
  2. last_checked_at < now() - make_interval(mins => scrape_interval_minutes)
     — an expression index on the sum is NOT possible: timestamptz +
     interval is only STABLE (timezone-dependent), and index expressions
     must be immutable (verified live, error 42P17). A partial index on
     last_checked_at still serves the pipeline cohort-anchor filter; the
     per-listing interval comparison stays a filter on top. If this branch
     ever dominates, the clean fix is a real next_due_at column maintained
     by the denorm gate writes — not an expression index.

Plain in-transaction builds (not CONCURRENTLY): autocommit_block() is
broken under this project's async alembic env (see 051's docstring);
worker writes queue behind the SHARE lock for the seconds the builds take.
"""

from __future__ import annotations

from alembic import op

revision = "052_stale_due_index"
down_revision = "051_pool_read_perf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL statement_timeout = '600s'")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_listing_never_checked
        ON fact_listing (marketplace_id)
        WHERE is_active AND last_checked_at IS NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_listing_checked_active
        ON fact_listing (last_checked_at)
        WHERE is_active AND last_checked_at IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_listing_never_checked")
    op.execute("DROP INDEX IF EXISTS idx_listing_checked_active")
