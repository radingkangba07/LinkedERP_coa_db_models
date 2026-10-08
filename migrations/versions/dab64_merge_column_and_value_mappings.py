"""dab64: merge column_mappings (dab58) and value_mappings (dab63) heads

Revision ID: dab64
Revises: dab58, dab63
Create Date: 2026-10-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "dab64"
down_revision: Union[str, Sequence[str], None] = ("dab58", "dab63")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
