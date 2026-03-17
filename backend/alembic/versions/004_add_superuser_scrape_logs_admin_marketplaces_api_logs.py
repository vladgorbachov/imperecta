"""Add superuser, scrape_logs, admin_marketplaces, api_logs.

Revision ID: 004_superuser_scrape_admin_api
Revises: 003_telegram_user_fields
Create Date: 2026-03-04

Changes:
- users: add is_superuser, force_password_change
- create scrape_logs table
- create admin_marketplaces table
- create api_logs table

Idempotent: tables may exist from create_all; use IF NOT EXISTS.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "004_superuser_scrape_admin_api"
down_revision: Union[str, None] = "003_telegram_user_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(connection, name: str) -> bool:
    return inspect(connection).has_table(name)


def upgrade() -> None:
    """Add superuser fields and new tables. Idempotent for create_all-created DB."""
    conn = op.get_bind()

    # users: add columns if not exist
    if not _table_exists(conn, "users"):
        raise RuntimeError("users table must exist (run 001-003 or create_all)")
    insp = inspect(conn)
    user_cols = {c["name"] for c in insp.get_columns("users")}
    if "is_superuser" not in user_cols:
        op.add_column(
            "users",
            sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default="false"),
        )
    if "force_password_change" not in user_cols:
        op.add_column(
            "users",
            sa.Column("force_password_change", sa.Boolean(), nullable=False, server_default="false"),
        )

    if not _table_exists(conn, "scrape_logs"):
        op.create_table(
            "scrape_logs",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("marketplace_id", sa.String(50), nullable=False),
        sa.Column("marketplace_name", sa.String(100), nullable=False),
        sa.Column(
            "competitor_product_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("url", sa.String(2048), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("price_found", sa.Numeric(12, 2), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("proxy_used", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["competitor_product_id"],
            ["competitor_products.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_scrape_logs_marketplace_id", "scrape_logs", ["marketplace_id"])
        op.create_index("ix_scrape_logs_created_at", "scrape_logs", ["created_at"])
        op.create_index(
            "ix_scrape_logs_marketplace_created",
            "scrape_logs",
            ["marketplace_id", "created_at"],
        )

    if not _table_exists(conn, "admin_marketplaces"):
        op.create_table(
            "admin_marketplaces",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("marketplace_id", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("base_url", sa.String(2048), nullable=False),
        sa.Column("country", sa.String(2), nullable=False, server_default="XX"),
        sa.Column("region", sa.String(20), nullable=False, server_default="other"),
        sa.Column("currency", sa.String(5), nullable=False, server_default="USD"),
        sa.Column("scraper_type", sa.String(50), nullable=False, server_default="generic"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_scrape_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_scrape_status", sa.String(20), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("total_scrapes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("successful_scrapes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_scrapes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("marketplace_id"),
        )

    if not _table_exists(conn, "api_logs"):
        op.create_table(
            "api_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("service", sa.String(30), nullable=False),
        sa.Column("endpoint", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_api_logs_service", "api_logs", ["service"])
        op.create_index("ix_api_logs_created_at", "api_logs", ["created_at"])


def downgrade() -> None:
    """Remove superuser fields and new tables."""
    op.drop_index("ix_api_logs_created_at", "api_logs")
    op.drop_index("ix_api_logs_service", "api_logs")
    op.drop_table("api_logs")

    op.drop_table("admin_marketplaces")

    op.drop_index("ix_scrape_logs_marketplace_created", "scrape_logs")
    op.drop_index("ix_scrape_logs_created_at", "scrape_logs")
    op.drop_index("ix_scrape_logs_marketplace_id", "scrape_logs")
    op.drop_table("scrape_logs")

    op.drop_column("users", "force_password_change")
    op.drop_column("users", "is_superuser")
