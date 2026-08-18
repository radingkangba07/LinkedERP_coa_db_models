"""dab49: restructure project_display_codes to support both COA and org projects

Revision ID: dab49
Revises: dab48
Create Date: 2026-08-10

Replaces the org_project_id primary key with a surrogate id, makes both
project_id and org_project_id nullable FKs, and adds a XOR check constraint
so that exactly one is set.  The global sequence counter per
(org_part, source_part, target_part) prefix is preserved and now shared
across both project types, guaranteeing unique display codes within an org.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "dab49"
down_revision = "dab48"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("project_display_codes")
    op.create_table(
        "project_display_codes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("org_project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("display_code", sa.String(50), nullable=False),
        sa.Column("org_part", sa.String(10), nullable=False),
        sa.Column("source_part", sa.String(10), nullable=False),
        sa.Column("target_part", sa.String(10), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_project_id"], ["org_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id"),
        sa.UniqueConstraint("org_project_id"),
        sa.UniqueConstraint("display_code"),
        sa.CheckConstraint(
            "(project_id IS NOT NULL AND org_project_id IS NULL) OR "
            "(project_id IS NULL AND org_project_id IS NOT NULL)",
            name="ck_display_codes_project_xor",
        ),
    )


def downgrade() -> None:
    op.drop_table("project_display_codes")
    op.create_table(
        "project_display_codes",
        sa.Column("org_project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_code", sa.String(50), nullable=False),
        sa.Column("org_part", sa.String(10), nullable=False),
        sa.Column("source_part", sa.String(10), nullable=False),
        sa.Column("target_part", sa.String(10), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["org_project_id"], ["org_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("org_project_id"),
        sa.UniqueConstraint("display_code"),
    )
