"""add workstream_stage table

Revision ID: dab14_workstream_stage
Revises: dab13_workstream
Create Date: 2026-07-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "dab14_workstream_stage"
down_revision: str = "dab13_workstream"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    try:
        conn = op.get_bind()
        if "workstream_stages" in sa.inspect(conn).get_table_names():
            return
    except sa.exc.NoInspectionAvailable:
        pass

    op.create_table(
        "workstream_stages",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True, nullable=False),
        sa.Column("workstream_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workstreams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("is_completed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_workstream_stages_workstream_id", "workstream_stages", ["workstream_id"])


def downgrade() -> None:
    op.drop_index("ix_workstream_stages_workstream_id", table_name="workstream_stages")
    op.drop_table("workstream_stages")
