"""add workstream_status_log table

Revision ID: dab15_workstream_status_log
Revises: dab14_workstream_stage
Create Date: 2026-07-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "dab15_workstream_status_log"
down_revision: str = "dab14_workstream_stage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workstream_status_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True, nullable=False),
        sa.Column("workstream_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workstreams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("previous_status", sa.String(50), nullable=False),
        sa.Column("new_status", sa.String(50), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_workstream_status_logs_workstream_id", "workstream_status_logs", ["workstream_id"])


def downgrade() -> None:
    op.drop_index("ix_workstream_status_logs_workstream_id", table_name="workstream_status_logs")
    op.drop_table("workstream_status_logs")
