"""add project_wizard_fields table

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-06-29 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "d6e7f8a9b0c1"
down_revision: Union[str, Sequence[str], None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "project_wizard_fields",
        sa.Column("project_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("source_vendor_id", sa.String(100), nullable=True),
        sa.Column("target_vendor_id", sa.String(100), nullable=True),
        sa.Column("source_connection_method", sa.String(100), nullable=True),
        sa.Column("target_connection_method", sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_wizard_fields_project_id",
            ondelete="CASCADE",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("project_wizard_fields")
