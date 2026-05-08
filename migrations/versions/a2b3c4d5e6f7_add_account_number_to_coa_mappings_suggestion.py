"""add source_account_number and target_account_number to coa_mappings_suggestion

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-05-08 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a2b3c4d5e6f7"
down_revision: str | Sequence[str] | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "coa_mappings_suggestion",
        sa.Column("source_account_number", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "coa_mappings_suggestion",
        sa.Column("target_account_number", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("coa_mappings_suggestion", "target_account_number")
    op.drop_column("coa_mappings_suggestion", "source_account_number")
