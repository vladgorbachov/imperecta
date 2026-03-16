"""Add global product pool and extend admin marketplaces.

Revision ID: 015_add_global_products_and_extend_marketplaces
Revises: 014_avatar_url_text
Create Date: 2026-03-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "015_add_global_products_and_extend_marketplaces"
down_revision: Union[str, None] = "014_avatar_url_text"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("admin_marketplaces") as batch_op:
        batch_op.add_column(
            sa.Column("product_quota", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("products_in_pool", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("custom_product_link_selector", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("custom_price_selector", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("custom_title_selector", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("custom_image_selector", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("custom_next_page_selector", sa.String(length=500), nullable=True))
        batch_op.add_column(
            sa.Column("requires_js", sa.Boolean(), nullable=False, server_default="false")
        )
        batch_op.add_column(
            sa.Column("rate_limit_delay", sa.Float(), nullable=False, server_default="2.0")
        )
        batch_op.add_column(
            sa.Column("max_concurrent_requests", sa.Integer(), nullable=False, server_default="3")
        )
        batch_op.add_column(sa.Column("last_discovery_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.drop_column("created_by")

    op.create_table(
        "global_products",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("marketplace_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("url_hash", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=1000), nullable=True),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("current_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("original_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="USD"),
        sa.Column("price_change_pct_24h", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("price_change_pct_7d", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("price_change_pct_30d", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("volatility_30d", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("last_scraped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scrape_error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_scraper_layer", sa.String(length=50), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["marketplace_id"],
            ["admin_marketplaces.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url_hash"),
    )
    op.create_index("ix_global_products_marketplace_id", "global_products", ["marketplace_id"])
    op.create_index("ix_global_products_status", "global_products", ["status"])
    op.create_index(
        "ix_global_products_marketplace_status",
        "global_products",
        ["marketplace_id", "status"],
    )
    op.create_index("ix_global_products_stale", "global_products", ["status", "last_scraped_at"])
    op.create_index("ix_global_products_gainers", "global_products", ["price_change_pct_24h"])
    op.create_index("ix_global_products_volatile", "global_products", ["volatility_30d"])
    op.create_index("ix_global_products_recent", "global_products", ["discovered_at"])

    op.create_table(
        "global_price_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("global_product_id", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("original_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="USD"),
        sa.Column("scraper_layer", sa.String(length=50), nullable=True),
        sa.Column("scraped_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["global_product_id"],
            ["global_products.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_global_price_snapshots_global_product_id",
        "global_price_snapshots",
        ["global_product_id"],
    )
    op.create_index(
        "ix_global_snapshots_product_time",
        "global_price_snapshots",
        ["global_product_id", "scraped_at"],
    )

    op.create_table(
        "discovery_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("marketplace_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="running"),
        sa.Column("pages_crawled", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("products_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("products_new", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["marketplace_id"],
            ["admin_marketplaces.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("discovery_logs")
    op.drop_table("global_price_snapshots")
    op.drop_table("global_products")

    with op.batch_alter_table("admin_marketplaces") as batch_op:
        batch_op.add_column(
            sa.Column(
                "created_by",
                postgresql.UUID(as_uuid=True),
                nullable=True,
            )
        )
        batch_op.create_foreign_key(
            "admin_marketplaces_created_by_fkey",
            "users",
            ["created_by"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.drop_column("last_discovery_at")
        batch_op.drop_column("max_concurrent_requests")
        batch_op.drop_column("rate_limit_delay")
        batch_op.drop_column("requires_js")
        batch_op.drop_column("custom_next_page_selector")
        batch_op.drop_column("custom_image_selector")
        batch_op.drop_column("custom_title_selector")
        batch_op.drop_column("custom_price_selector")
        batch_op.drop_column("custom_product_link_selector")
        batch_op.drop_column("products_in_pool")
        batch_op.drop_column("product_quota")
