"""dab51: rename workstreams.name to scope_name

Revision ID: dab51
Revises: dab50
Create Date: 2026-08-11
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
from sqlalchemy import inspect

revision: str = "dab51"
down_revision: Union[str, Sequence[str], None] = "dab50"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    cols = [c["name"] for c in inspector.get_columns("workstreams")]
    if "name" in cols:
        op.alter_column("workstreams", "name", new_column_name="scope_name")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    cols = [c["name"] for c in inspector.get_columns("workstreams")]
    if "scope_name" in cols:
        op.alter_column("workstreams", "scope_name", new_column_name="name")
