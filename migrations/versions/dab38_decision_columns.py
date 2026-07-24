"""add fix_type and status to item_profile_decisions, drop unique constraint

Revision ID: dab38_decision_columns
Revises: dab36_semantic_role
Create Date: 2026-07-24

  item_profile_decisions.fix_type  — varchar(50): fix variant for apply_fix decisions
  item_profile_decisions.status    — varchar(20): pending | undone
  drop uq_decision_run_field       — allow re-decisions after undo
  widen action column to varchar(50)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "dab38_decision_columns"
down_revision: str = "dab36_semantic_role"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_decision_run_field", "item_profile_decisions", type_="unique")
    op.alter_column(
        "item_profile_decisions",
        "action",
        existing_type=sa.String(20),
        type_=sa.String(50),
        existing_nullable=False,
    )
    op.add_column("item_profile_decisions", sa.Column("fix_type", sa.String(50), nullable=True))
    op.add_column(
        "item_profile_decisions",
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
    )


def downgrade() -> None:
    op.drop_column("item_profile_decisions", "status")
    op.drop_column("item_profile_decisions", "fix_type")
    op.alter_column(
        "item_profile_decisions",
        "action",
        existing_type=sa.String(50),
        type_=sa.String(20),
        existing_nullable=False,
    )
    op.create_unique_constraint(
        "uq_decision_run_field", "item_profile_decisions", ["run_id", "field_name"]
    )
