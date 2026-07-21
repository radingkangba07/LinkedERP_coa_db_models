"""add erp_compatibility_rules table

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-06-26 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, Sequence[str], None] = "b4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("erp_compatibility_rules"):
        op.create_table(
            "erp_compatibility_rules",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("source_product_id", sa.String(100), nullable=False),
            sa.Column("target_product_id", sa.String(100), nullable=False),
            sa.Column("connection_method_id", sa.String(100), nullable=True),
            sa.Column("is_compatible", sa.Boolean(), nullable=False),
            sa.Column("incompatibility_reason", sa.Text(), nullable=True),
        )
        op.create_index("ix_compat_source", "erp_compatibility_rules", ["source_product_id"])
        op.create_index("ix_compat_target", "erp_compatibility_rules", ["target_product_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_compat_target", table_name="erp_compatibility_rules")
    op.drop_index("ix_compat_source", table_name="erp_compatibility_rules")
    op.drop_table("erp_compatibility_rules")
