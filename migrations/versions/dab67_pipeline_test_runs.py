"""dab63: add pipeline_test_runs table (wizard step 7)

Revision ID: dab67
Revises: dab66
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "dab67"
down_revision: Union[str, Sequence[str], None] = "dab66"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("pipeline_test_runs"):
        return
    op.create_table(
        "pipeline_test_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="'pending'"),
        sa.Column("triggered_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rows_attempted", sa.Integer, nullable=True),
        sa.Column("rows_passed", sa.Integer, nullable=True),
        sa.Column("rows_failed", sa.Integer, nullable=True),
        sa.Column("failure_summary", JSONB, nullable=True),
        sa.Column("sample_failures", JSONB, nullable=True),
        sa.Column("error_detail", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('pending','running','complete','failed')",
            name="ck_pipeline_test_runs_status",
        ),
    )
    op.create_index("ix_pipeline_test_runs_run_id", "pipeline_test_runs", ["run_id"])
    op.create_index("ix_pipeline_test_runs_status", "pipeline_test_runs", ["status"])
    # Prevent two active test runs for the same pipeline run simultaneously.
    op.create_index(
        "uix_pipeline_test_runs_run_active",
        "pipeline_test_runs",
        ["run_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )


def downgrade() -> None:
    op.drop_index("uix_pipeline_test_runs_run_active", table_name="pipeline_test_runs")
    op.drop_index("ix_pipeline_test_runs_status", table_name="pipeline_test_runs")
    op.drop_index("ix_pipeline_test_runs_run_id", table_name="pipeline_test_runs")
    op.drop_table("pipeline_test_runs")
