"""add source profile stats columns to item_profile_runs

Revision ID: dab42_source_profile_stats
Revises: dab41_odoo_target
Create Date: 2026-07-27

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "dab42_source_profile_stats"
down_revision: str = "dab41_odoo_target"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("item_profile_runs", sa.Column("invalid_uom_count", sa.Integer(), nullable=True))
    op.add_column("item_profile_runs", sa.Column("missing_product_type_count", sa.Integer(), nullable=True))
    op.add_column("item_profile_runs", sa.Column("interpretation_text", sa.Text(), nullable=True))
    op.add_column("item_profile_runs", sa.Column("recommended_actions", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("item_profile_runs", "recommended_actions")
    op.drop_column("item_profile_runs", "interpretation_text")
    op.drop_column("item_profile_runs", "missing_product_type_count")
    op.drop_column("item_profile_runs", "invalid_uom_count")
