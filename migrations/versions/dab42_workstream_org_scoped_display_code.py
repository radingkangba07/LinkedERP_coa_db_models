"""workstream: add org_id as direct link to organisation

Revision ID: dab42_workstream_org_display
Revises: dab26_stage_weight_reseed
Create Date: 2026-08-03

Adds org_id to workstreams so each workstream is directly linked to its
organisation UUID without having to traverse project_id → projects.org_id.

The display_code uniqueness constraint (project_id, display_code) is
unchanged — display codes remain project-scoped and every project can
start from MD-001. The workstream UUID (id) is the globally unique
backend identifier.

Steps:
  1. Add org_id column (nullable) with FK to organizations.id
  2. Backfill org_id from projects.org_id via project_id
  3. Set org_id NOT NULL
  4. Add index on org_id
"""

from alembic import op
import sqlalchemy as sa

revision: str = "dab42_workstream_org_display"
down_revision: str = "dab26_stage_weight_reseed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add org_id as nullable first so existing rows don't violate NOT NULL
    op.add_column(
        "workstreams",
        sa.Column("org_id", sa.UUID(), nullable=True),
    )

    # 2. Backfill org_id from the parent project
    op.execute(
        """
        UPDATE workstreams w
        SET org_id = p.org_id
        FROM projects p
        WHERE w.project_id = p.id
        """
    )

    # 3. Enforce NOT NULL now that every row has a value
    op.alter_column("workstreams", "org_id", nullable=False)

    # 4. Add FK constraint to organizations
    op.create_foreign_key(
        "fk_workstreams_org_id",
        "workstreams",
        "organizations",
        ["org_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 5. Add index on org_id for query performance
    op.create_index("ix_workstreams_org_id", "workstreams", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_workstreams_org_id", table_name="workstreams")
    op.drop_constraint("fk_workstreams_org_id", "workstreams", type_="foreignkey")
    op.drop_column("workstreams", "org_id")
