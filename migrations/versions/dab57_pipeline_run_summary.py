"""dab57: add run_summary JSONB column to pipeline_runs

Revision ID: dab57
Revises: dab56
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "dab57"
down_revision: Union[str, Sequence[str], None] = "dab56"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pipeline_runs", sa.Column("run_summary", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("pipeline_runs", "run_summary")
