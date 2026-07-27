"""add migration_key_field to item_profile_runs

Revision ID: dab38b_migration_key
Revises: dab38_decision_columns
Create Date: 2026-07-27
"""

from alembic import op
import sqlalchemy as sa

revision = "dab38b_migration_key"
down_revision = "dab38_decision_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "item_profile_runs",
        sa.Column("migration_key_field", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("item_profile_runs", "migration_key_field")
