"""dim_marketplace.access_mode — how a shop is reachable, not how it renders.

Revision ID: 047_marketplace_access_mode
Revises: 046_gate_dim_brand_category
Create Date: 2026-09-15

The 2026-09-14 validation sweep proved requires_js conflates two different
facts: some shops need JS rendering, others block datacenter IPs outright and
need the residential proxy regardless of rendering. access_mode makes the
fetch policy explicit per marketplace:

  direct       - plain HTTP first (default)
  render       - headless browser first (JS storefront)
  proxy        - residential proxy API only (datacenter IPs blocked)
  proxy_render - residential proxy with JS rendering

Existing rows keep 'direct'; requires_js remains a legacy render hint used
when access_mode is 'direct'.
"""

from __future__ import annotations

from alembic import op

revision = "047_marketplace_access_mode"
down_revision = "046_gate_dim_brand_category"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE dim_marketplace "
        "ADD COLUMN IF NOT EXISTS access_mode varchar(16) NOT NULL DEFAULT 'direct'"
    )
    op.execute(
        "ALTER TABLE dim_marketplace "
        "ADD CONSTRAINT ck_dim_marketplace_access_mode "
        "CHECK (access_mode IN ('direct', 'render', 'proxy', 'proxy_render'))"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE dim_marketplace DROP CONSTRAINT IF EXISTS ck_dim_marketplace_access_mode"
    )
    op.execute("ALTER TABLE dim_marketplace DROP COLUMN IF EXISTS access_mode")
