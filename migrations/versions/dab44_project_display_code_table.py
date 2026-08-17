"""projects: move display code columns to project_display_codes table

Revision ID: dab44_project_display_code_table
Revises: dab42_workstream_org_display
Create Date: 2026-08-04

Extracts five display-code columns from the projects table into a new
1:1 child table project_display_codes:

  display_code      → project_display_codes.display_code  (UNIQUE)
  display_code_org  → project_display_codes.org_part
  display_code_src  → project_display_codes.source_part
  display_code_tgt  → project_display_codes.target_part
  display_code_seq  → project_display_codes.seq

Draft projects (display_code IS NULL) have no row in the new table.
"""

from alembic import op
import sqlalchemy as sa

revision: str = "dab44_project_display_code_table"
down_revision: str = "dab42_workstream_org_display"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create the new table
    op.create_table(
        "project_display_codes",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("display_code", sa.String(50), nullable=False),
        sa.Column("org_part", sa.String(10), nullable=False),
        sa.Column("source_part", sa.String(10), nullable=False),
        sa.Column("target_part", sa.String(10), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("project_id"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_display_codes_project_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("display_code", name="uq_project_display_codes_display_code"),
    )

    # 2. Backfill from projects — only rows that already have a display code
    op.execute(
        """
        INSERT INTO project_display_codes
            (project_id, display_code, org_part, source_part, target_part, seq)
        SELECT
            id,
            display_code,
            display_code_org,
            display_code_src,
            display_code_tgt,
            display_code_seq
        FROM projects
        WHERE display_code IS NOT NULL
          AND display_code_org IS NOT NULL
          AND display_code_src IS NOT NULL
          AND display_code_tgt IS NOT NULL
          AND display_code_seq IS NOT NULL
        """
    )

    # 3. Drop the unique constraint (IF EXISTS — some DB paths never had it) then the five columns
    op.execute("ALTER TABLE projects DROP CONSTRAINT IF EXISTS projects_display_code_key")
    op.drop_column("projects", "display_code")
    op.drop_column("projects", "display_code_org")
    op.drop_column("projects", "display_code_src")
    op.drop_column("projects", "display_code_tgt")
    op.drop_column("projects", "display_code_seq")


def downgrade() -> None:
    # 1. Restore the five columns (all nullable — some projects may not have a code)
    op.add_column("projects", sa.Column("display_code", sa.String(50), nullable=True))
    op.add_column("projects", sa.Column("display_code_org", sa.String(10), nullable=True))
    op.add_column("projects", sa.Column("display_code_src", sa.String(10), nullable=True))
    op.add_column("projects", sa.Column("display_code_tgt", sa.String(10), nullable=True))
    op.add_column("projects", sa.Column("display_code_seq", sa.Integer(), nullable=True))

    # 2. Backfill from project_display_codes
    op.execute(
        """
        UPDATE projects p
        SET
            display_code     = dc.display_code,
            display_code_org = dc.org_part,
            display_code_src = dc.source_part,
            display_code_tgt = dc.target_part,
            display_code_seq = dc.seq
        FROM project_display_codes dc
        WHERE p.id = dc.project_id
        """
    )

    # 3. Re-add the unique constraint and the named index that dab16 created
    op.create_unique_constraint("projects_display_code_key", "projects", ["display_code"])
    op.create_index("ix_projects_display_code", "projects", ["display_code"], unique=True)

    # 4. Drop the new table
    op.drop_table("project_display_codes")
