"""dab50: rename project_master_data_selections.data_type to scope_name

Revision ID: dab50
Revises: dab49
Create Date: 2026-08-11
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
from sqlalchemy import inspect

revision: str = "dab50"
down_revision: Union[str, Sequence[str], None] = "dab49"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    cols = [c["name"] for c in inspector.get_columns("project_master_data_selections")]
    if "data_type" in cols:
        op.alter_column("project_master_data_selections", "data_type", new_column_name="scope_name")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    cols = [c["name"] for c in inspector.get_columns("project_master_data_selections")]
    if "scope_name" in cols:
        op.alter_column("project_master_data_selections", "scope_name", new_column_name="data_type")
