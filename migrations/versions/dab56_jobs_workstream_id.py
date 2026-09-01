"""dab56: add workstream_id to jobs

Revision ID: dab56
Revises: dab55
Create Date: 2026-08-27

Adds a nullable workstream_id FK to jobs so a profile (or other wizard) job
can address the workstream whose pack it must write. Mirrors the project_files
pattern. The existing project_xor constraint is unchanged — MD jobs carry
org_project_id alongside workstream_id.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "dab56"
down_revision: Union[str, Sequence[str], None] = "dab55"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("workstream_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_jobs_workstream_id",
        "jobs",
        "workstreams",
        ["workstream_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_jobs_workstream_id", "jobs", ["workstream_id"])


def downgrade() -> None:
    op.drop_index("ix_jobs_workstream_id", table_name="jobs")
    op.drop_constraint("fk_jobs_workstream_id", "jobs", type_="foreignkey")
    op.drop_column("jobs", "workstream_id")
