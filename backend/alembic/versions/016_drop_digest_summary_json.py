"""Drop unused digests.summary_json column.

Revision ID: 016_drop_digest_summary_json
Revises: 015_add_global_products_and_extend_marketplaces
Create Date: 2026-03-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "016_drop_digest_summary_json"
down_revision: Union[str, None] = "015_global_products"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("digests") as batch_op:
        batch_op.drop_column("summary_json")


def downgrade() -> None:
    with op.batch_alter_table("digests") as batch_op:
        batch_op.add_column(sa.Column("summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
