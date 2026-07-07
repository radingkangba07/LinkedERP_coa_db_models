"""add workstream table

Revision ID: dab13_workstream
Revises: dab12_workstream_category
Create Date: 2026-07-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "dab13_workstream"
down_revision: str = "dab12_workstream_category"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    try:
        conn = op.get_bind()
        if "workstreams" in sa.inspect(conn).get_table_names():
            return
    except sa.exc.NoInspectionAvailable:
        pass

    op.create_table(
        "workstreams",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True, nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workstream_categories.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("display_code", sa.String(20), nullable=False),
        sa.Column("status", sa.String(50), server_default="not_started", nullable=False),
        sa.Column("current_stage", sa.String(50), server_default="erp_select", nullable=False),
        sa.Column("is_included", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.UniqueConstraint("project_id", "display_code", name="uq_workstream_project_display_code"),
    )
    op.create_index("ix_workstreams_project_id", "workstreams", ["project_id"])
    op.create_index("ix_workstreams_status", "workstreams", ["status"])


def downgrade() -> None:
    op.drop_index("ix_workstreams_status", table_name="workstreams")
    op.drop_index("ix_workstreams_project_id", table_name="workstreams")
    op.drop_table("workstreams")
