"""dab48: add org_projects and decouple non-COA scopes from projects

Revision ID: dab48
Revises: 71317be
Create Date: 2026-08-10

- Create org_projects table (umbrella container for 8 non-COA scopes)
- Create org_project_access table
- Create org_project_wizard_fields table
- project_display_codes: replace project_id PK with org_project_id
- workstreams: project_id nullable, add org_project_id, XOR check constraint
- project_files: project_id nullable, add org_project_id, XOR check constraint
- jobs: project_id nullable, add org_project_id, XOR check constraint
- project_master_data_selections: project_id nullable, add org_project_id, XOR check
- project_opening_balance_selections: project_id nullable, add org_project_id, XOR check
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "dab48"
down_revision = "dab47_packs_and_decisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Create org_projects ────────────────────────────────────────────────
    op.create_table(
        "org_projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_system", sa.String(100), server_default="", nullable=False),
        sa.Column("target_system", sa.String(100), server_default="", nullable=False),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("current_step", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_org_projects_org_id", "org_projects", ["org_id"])
    op.create_index("ix_org_projects_status", "org_projects", ["status"])

    # ── 2. Create org_project_access ──────────────────────────────────────────
    op.create_table(
        "org_project_access",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission", sa.String(20), server_default="viewer", nullable=False),
        sa.Column("assigned_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_project_id"], ["org_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "org_project_id", name="uq_user_org_project"),
    )
    op.create_index("ix_org_project_access_user_id", "org_project_access", ["user_id"])
    op.create_index("ix_org_project_access_org_project_id", "org_project_access", ["org_project_id"])

    # ── 3. Create org_project_wizard_fields ───────────────────────────────────
    op.create_table(
        "org_project_wizard_fields",
        sa.Column("org_project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_vendor_id", sa.String(100), nullable=True),
        sa.Column("target_vendor_id", sa.String(100), nullable=True),
        sa.Column("source_connection_method", sa.String(100), nullable=True),
        sa.Column("target_connection_method", sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(["org_project_id"], ["org_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("org_project_id"),
    )

    # ── 4. project_display_codes: swap project_id PK → org_project_id ────────
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

    # ── 5. workstreams: make project_id nullable, add org_project_id ──────────
    op.alter_column("workstreams", "project_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.add_column("workstreams", sa.Column("org_project_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_workstreams_org_project_id", "workstreams", "org_projects", ["org_project_id"], ["id"], ondelete="CASCADE"
    )
    op.create_check_constraint(
        "ck_workstream_project_xor",
        "workstreams",
        "(project_id IS NOT NULL AND org_project_id IS NULL) OR "
        "(project_id IS NULL AND org_project_id IS NOT NULL)",
    )
    op.create_index("ix_workstreams_org_project_id", "workstreams", ["org_project_id"])
    op.create_unique_constraint(
        "uq_workstream_org_project_display_code", "workstreams", ["org_project_id", "display_code"]
    )
    op.create_unique_constraint(
        "uq_workstream_org_project_entity", "workstreams", ["org_project_id", "entity_id"]
    )

    # ── 6. project_files: make project_id nullable, add org_project_id ────────
    op.alter_column("project_files", "project_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.add_column("project_files", sa.Column("org_project_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_project_files_org_project_id", "project_files", "org_projects", ["org_project_id"], ["id"], ondelete="CASCADE"
    )
    op.create_check_constraint(
        "ck_project_files_project_xor",
        "project_files",
        "(project_id IS NOT NULL AND org_project_id IS NULL) OR "
        "(project_id IS NULL AND org_project_id IS NOT NULL)",
    )
    op.create_index("ix_project_files_org_project_id", "project_files", ["org_project_id"])

    # ── 7. jobs: make project_id nullable, add org_project_id ─────────────────
    op.alter_column("jobs", "project_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.add_column("jobs", sa.Column("org_project_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_jobs_org_project_id", "jobs", "org_projects", ["org_project_id"], ["id"], ondelete="CASCADE"
    )
    op.create_check_constraint(
        "ck_jobs_project_xor",
        "jobs",
        "(project_id IS NOT NULL AND org_project_id IS NULL) OR "
        "(project_id IS NULL AND org_project_id IS NOT NULL)",
    )
    op.create_index("ix_jobs_org_project_id", "jobs", ["org_project_id"])

    # ── 8. project_master_data_selections: project_id nullable, add org_project_id
    op.alter_column(
        "project_master_data_selections", "project_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True
    )
    op.add_column(
        "project_master_data_selections",
        sa.Column("org_project_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_master_data_sel_org_project_id",
        "project_master_data_selections",
        "org_projects",
        ["org_project_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_check_constraint(
        "ck_master_data_sel_project_xor",
        "project_master_data_selections",
        "(project_id IS NOT NULL AND org_project_id IS NULL) OR "
        "(project_id IS NULL AND org_project_id IS NOT NULL)",
    )
    op.create_index(
        "ix_project_master_data_sel_org_project_id", "project_master_data_selections", ["org_project_id"]
    )

    # ── 9. project_opening_balance_selections: project_id nullable, add org_project_id
    op.alter_column(
        "project_opening_balance_selections", "project_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True
    )
    op.add_column(
        "project_opening_balance_selections",
        sa.Column("org_project_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_opening_bal_sel_org_project_id",
        "project_opening_balance_selections",
        "org_projects",
        ["org_project_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_check_constraint(
        "ck_opening_bal_sel_project_xor",
        "project_opening_balance_selections",
        "(project_id IS NOT NULL AND org_project_id IS NULL) OR "
        "(project_id IS NULL AND org_project_id IS NOT NULL)",
    )
    op.create_index(
        "ix_project_opening_bal_sel_org_project_id", "project_opening_balance_selections", ["org_project_id"]
    )


def downgrade() -> None:
    # ── 9. project_opening_balance_selections ─────────────────────────────────
    op.drop_index("ix_project_opening_bal_sel_org_project_id", "project_opening_balance_selections")
    op.drop_constraint("ck_opening_bal_sel_project_xor", "project_opening_balance_selections", type_="check")
    op.drop_constraint("fk_opening_bal_sel_org_project_id", "project_opening_balance_selections", type_="foreignkey")
    op.drop_column("project_opening_balance_selections", "org_project_id")
    op.alter_column(
        "project_opening_balance_selections", "project_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False
    )

    # ── 8. project_master_data_selections ─────────────────────────────────────
    op.drop_index("ix_project_master_data_sel_org_project_id", "project_master_data_selections")
    op.drop_constraint("ck_master_data_sel_project_xor", "project_master_data_selections", type_="check")
    op.drop_constraint("fk_master_data_sel_org_project_id", "project_master_data_selections", type_="foreignkey")
    op.drop_column("project_master_data_selections", "org_project_id")
    op.alter_column(
        "project_master_data_selections", "project_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False
    )

    # ── 7. jobs ───────────────────────────────────────────────────────────────
    op.drop_index("ix_jobs_org_project_id", "jobs")
    op.drop_constraint("ck_jobs_project_xor", "jobs", type_="check")
    op.drop_constraint("fk_jobs_org_project_id", "jobs", type_="foreignkey")
    op.drop_column("jobs", "org_project_id")
    op.alter_column("jobs", "project_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)

    # ── 6. project_files ──────────────────────────────────────────────────────
    op.drop_index("ix_project_files_org_project_id", "project_files")
    op.drop_constraint("ck_project_files_project_xor", "project_files", type_="check")
    op.drop_constraint("fk_project_files_org_project_id", "project_files", type_="foreignkey")
    op.drop_column("project_files", "org_project_id")
    op.alter_column("project_files", "project_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)

    # ── 5. workstreams ────────────────────────────────────────────────────────
    op.drop_constraint("uq_workstream_org_project_entity", "workstreams", type_="unique")
    op.drop_constraint("uq_workstream_org_project_display_code", "workstreams", type_="unique")
    op.drop_index("ix_workstreams_org_project_id", "workstreams")
    op.drop_constraint("ck_workstream_project_xor", "workstreams", type_="check")
    op.drop_constraint("fk_workstreams_org_project_id", "workstreams", type_="foreignkey")
    op.drop_column("workstreams", "org_project_id")
    op.alter_column("workstreams", "project_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)

    # ── 4. project_display_codes: restore project_id PK ──────────────────────
    op.drop_table("project_display_codes")
    op.create_table(
        "project_display_codes",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_code", sa.String(50), nullable=False),
        sa.Column("org_part", sa.String(10), nullable=False),
        sa.Column("source_part", sa.String(10), nullable=False),
        sa.Column("target_part", sa.String(10), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id"),
        sa.UniqueConstraint("display_code"),
    )

    # ── 3. org_project_wizard_fields ──────────────────────────────────────────
    op.drop_table("org_project_wizard_fields")

    # ── 2. org_project_access ─────────────────────────────────────────────────
    op.drop_table("org_project_access")

    # ── 1. org_projects ───────────────────────────────────────────────────────
    op.drop_table("org_projects")
