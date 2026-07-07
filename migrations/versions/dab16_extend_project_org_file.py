"""extend project, organisation, and file tables with workstream-related fields

Revision ID: dab16_extend_project_org_file
Revises: dab15_workstream_status_log
Create Date: 2026-07-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "dab16_extend_project_org_file"
down_revision: str = "dab15_workstream_status_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    try:
        conn = op.get_bind()
        existing_cols = [c["name"] for c in sa.inspect(conn).get_columns("projects")]
        if "display_code" in existing_cols:
            return
    except sa.exc.NoInspectionAvailable:
        pass

    # project — display code component columns
    op.add_column("projects", sa.Column("display_code", sa.String(50), nullable=True))
    op.add_column("projects", sa.Column("display_code_org", sa.String(10), nullable=True))
    op.add_column("projects", sa.Column("display_code_src", sa.String(10), nullable=True))
    op.add_column("projects", sa.Column("display_code_tgt", sa.String(10), nullable=True))
    op.add_column("projects", sa.Column("display_code_seq", sa.Integer(), nullable=True))
    op.create_index("ix_projects_display_code", "projects", ["display_code"], unique=True)

    # organisation — short alphanumeric code for display code generation
    op.add_column("organizations", sa.Column("code", sa.String(10), nullable=True))
    op.create_index("ix_organizations_code", "organizations", ["code"], unique=True)

    # project_files — workstream association for upload-stage files
    op.add_column(
        "project_files",
        sa.Column(
            "workstream_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workstreams.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_project_files_workstream_id", "project_files", ["workstream_id"])


def downgrade() -> None:
    op.drop_index("ix_project_files_workstream_id", table_name="project_files")
    op.drop_column("project_files", "workstream_id")

    op.drop_index("ix_organizations_code", table_name="organizations")
    op.drop_column("organizations", "code")

    op.drop_index("ix_projects_display_code", table_name="projects")
    op.drop_column("projects", "display_code_seq")
    op.drop_column("projects", "display_code_tgt")
    op.drop_column("projects", "display_code_src")
    op.drop_column("projects", "display_code_org")
    op.drop_column("projects", "display_code")
