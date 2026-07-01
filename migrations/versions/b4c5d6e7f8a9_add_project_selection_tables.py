"""add project_master_data_selections and project_opening_balance_selections

Revision ID: b4c5d6e7f8a9
Revises: a2b3c4d5e6f7
Create Date: 2026-06-26 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

# revision identifiers, used by Alembic.
revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, Sequence[str], None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "project_master_data_selections",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("data_type", sa.String(100), nullable=False),
        sa.Column("selected", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index(
        "ix_project_master_data_project_id",
        "project_master_data_selections",
        ["project_id"],
    )

    op.create_table(
        "project_opening_balance_selections",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("account_type", sa.String(100), nullable=False),
        sa.Column("include", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index(
        "ix_project_opening_balance_project_id",
        "project_opening_balance_selections",
        ["project_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_project_opening_balance_project_id", table_name="project_opening_balance_selections")
    op.drop_table("project_opening_balance_selections")
    op.drop_index("ix_project_master_data_project_id", table_name="project_master_data_selections")
    op.drop_table("project_master_data_selections")
