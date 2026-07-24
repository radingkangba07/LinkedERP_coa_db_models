"""add fields_processed to item_profile_runs for staged progress tracking

Revision ID: dab40_fields_processed
Revises: dab38b_migration_key
Create Date: 2026-07-24

  item_profile_runs.fields_processed — integer: fields profiled so far,
    updated at each pipeline stage for frontend progress polling.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "dab40_fields_processed"
down_revision: str = "dab38b_migration_key"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("item_profile_runs", sa.Column("fields_processed", sa.Integer, nullable=True))


def downgrade() -> None:
    op.drop_column("item_profile_runs", "fields_processed")
