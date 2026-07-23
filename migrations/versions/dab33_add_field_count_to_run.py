"""add field_count to item_profile_runs

Revision ID: dab33_add_field_count_to_run
Revises: dab32_item_profile_schema
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "dab33_add_field_count_to_run"
down_revision: str = "dab32_item_profile_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "item_profile_runs",
        sa.Column("field_count", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("item_profile_runs", "field_count")
