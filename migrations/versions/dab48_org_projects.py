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
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision = "dab48"
down_revision = "dab47_packs_and_decisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    # ── 1. Create org_projects ────────────────────────────────────────────────
    if not inspector.has_table("org_projects"):
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
    org_proj_indexes = {i["name"] for i in inspector.get_indexes("org_projects")} if inspector.has_table("org_projects") else set()
    if "ix_org_projects_org_id" not in org_proj_indexes:
        op.create_index("ix_org_projects_org_id", "org_projects", ["org_id"])
    if "ix_org_projects_status" not in org_proj_indexes:
        op.create_index("ix_org_projects_status", "org_projects", ["status"])

    # ── 2. Create org_project_access ──────────────────────────────────────────
    if not inspector.has_table("org_project_access"):
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
    opa_indexes = {i["name"] for i in inspector.get_indexes("org_project_access")} if inspector.has_table("org_project_access") else set()
    if "ix_org_project_access_user_id" not in opa_indexes:
        op.create_index("ix_org_project_access_user_id", "org_project_access", ["user_id"])
    if "ix_org_project_access_org_project_id" not in opa_indexes:
        op.create_index("ix_org_project_access_org_project_id", "org_project_access", ["org_project_id"])

    # ── 3. Create org_project_wizard_fields ───────────────────────────────────
    if not inspector.has_table("org_project_wizard_fields"):
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
    # Guard: if the table already has org_project_id as its PK column, skip the swap.
    pdc_cols = {c["name"] for c in inspector.get_columns("project_display_codes")} if inspector.has_table("project_display_codes") else set()
    if "org_project_id" not in pdc_cols:
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
    # ALTER COLUMN … DROP NOT NULL is idempotent in PostgreSQL.
    op.alter_column("workstreams", "project_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    ws_cols = {c["name"] for c in inspector.get_columns("workstreams")}
    ws_indexes = {i["name"] for i in inspector.get_indexes("workstreams")}
    ws_fks = {fk["name"] for fk in inspector.get_foreign_keys("workstreams")}
    ws_checks = {ck["name"] for ck in inspector.get_check_constraints("workstreams")}
    ws_uqs = {uq["name"] for uq in inspector.get_unique_constraints("workstreams")}
    if "org_project_id" not in ws_cols:
        op.add_column("workstreams", sa.Column("org_project_id", postgresql.UUID(as_uuid=True), nullable=True))
    if "fk_workstreams_org_project_id" not in ws_fks:
        op.create_foreign_key(
            "fk_workstreams_org_project_id", "workstreams", "org_projects", ["org_project_id"], ["id"], ondelete="CASCADE"
        )
    if "ck_workstream_project_xor" not in ws_checks:
        bind.execute(sa.text(
            "UPDATE workstreams SET org_project_id = NULL "
            "WHERE project_id IS NOT NULL AND org_project_id IS NOT NULL"
        ))
        bind.execute(sa.text(
            "DELETE FROM workstreams WHERE project_id IS NULL AND org_project_id IS NULL"
        ))
        op.create_check_constraint(
            "ck_workstream_project_xor",
            "workstreams",
            "(project_id IS NOT NULL AND org_project_id IS NULL) OR "
            "(project_id IS NULL AND org_project_id IS NOT NULL)",
        )
    if "ix_workstreams_org_project_id" not in ws_indexes:
        op.create_index("ix_workstreams_org_project_id", "workstreams", ["org_project_id"])
    if "uq_workstream_org_project_display_code" not in ws_uqs:
        op.create_unique_constraint(
            "uq_workstream_org_project_display_code", "workstreams", ["org_project_id", "display_code"]
        )
    if "uq_workstream_org_project_entity" not in ws_uqs:
        op.create_unique_constraint(
            "uq_workstream_org_project_entity", "workstreams", ["org_project_id", "entity_id"]
        )

    # ── 6. project_files: make project_id nullable, add org_project_id ────────
    op.alter_column("project_files", "project_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    pf_cols = {c["name"] for c in inspector.get_columns("project_files")}
    pf_indexes = {i["name"] for i in inspector.get_indexes("project_files")}
    pf_fks = {fk["name"] for fk in inspector.get_foreign_keys("project_files")}
    pf_checks = {ck["name"] for ck in inspector.get_check_constraints("project_files")}
    if "org_project_id" not in pf_cols:
        op.add_column("project_files", sa.Column("org_project_id", postgresql.UUID(as_uuid=True), nullable=True))
    if "fk_project_files_org_project_id" not in pf_fks:
        op.create_foreign_key(
            "fk_project_files_org_project_id", "project_files", "org_projects", ["org_project_id"], ["id"], ondelete="CASCADE"
        )
    if "ck_project_files_project_xor" not in pf_checks:
        bind.execute(sa.text(
            "UPDATE project_files SET org_project_id = NULL "
            "WHERE project_id IS NOT NULL AND org_project_id IS NOT NULL"
        ))
        bind.execute(sa.text(
            "DELETE FROM project_files WHERE project_id IS NULL AND org_project_id IS NULL"
        ))
        op.create_check_constraint(
            "ck_project_files_project_xor",
            "project_files",
            "(project_id IS NOT NULL AND org_project_id IS NULL) OR "
            "(project_id IS NULL AND org_project_id IS NOT NULL)",
        )
    if "ix_project_files_org_project_id" not in pf_indexes:
        op.create_index("ix_project_files_org_project_id", "project_files", ["org_project_id"])

    # ── 7. jobs: make project_id nullable, add org_project_id ─────────────────
    op.alter_column("jobs", "project_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    j_cols = {c["name"] for c in inspector.get_columns("jobs")}
    j_indexes = {i["name"] for i in inspector.get_indexes("jobs")}
    j_fks = {fk["name"] for fk in inspector.get_foreign_keys("jobs")}
    j_checks = {ck["name"] for ck in inspector.get_check_constraints("jobs")}
    if "org_project_id" not in j_cols:
        op.add_column("jobs", sa.Column("org_project_id", postgresql.UUID(as_uuid=True), nullable=True))
    if "fk_jobs_org_project_id" not in j_fks:
        op.create_foreign_key(
            "fk_jobs_org_project_id", "jobs", "org_projects", ["org_project_id"], ["id"], ondelete="CASCADE"
        )
    if "ck_jobs_project_xor" not in j_checks:
        bind.execute(sa.text(
            "UPDATE jobs SET org_project_id = NULL "
            "WHERE project_id IS NOT NULL AND org_project_id IS NOT NULL"
        ))
        bind.execute(sa.text(
            "DELETE FROM jobs WHERE project_id IS NULL AND org_project_id IS NULL"
        ))
        op.create_check_constraint(
            "ck_jobs_project_xor",
            "jobs",
            "(project_id IS NOT NULL AND org_project_id IS NULL) OR "
            "(project_id IS NULL AND org_project_id IS NOT NULL)",
        )
    if "ix_jobs_org_project_id" not in j_indexes:
        op.create_index("ix_jobs_org_project_id", "jobs", ["org_project_id"])

    # ── 8. project_master_data_selections: project_id nullable, add org_project_id
    op.alter_column(
        "project_master_data_selections", "project_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True
    )
    mds_cols = {c["name"] for c in inspector.get_columns("project_master_data_selections")}
    mds_indexes = {i["name"] for i in inspector.get_indexes("project_master_data_selections")}
    mds_fks = {fk["name"] for fk in inspector.get_foreign_keys("project_master_data_selections")}
    mds_checks = {ck["name"] for ck in inspector.get_check_constraints("project_master_data_selections")}
    if "org_project_id" not in mds_cols:
        op.add_column(
            "project_master_data_selections",
            sa.Column("org_project_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
    if "fk_master_data_sel_org_project_id" not in mds_fks:
        op.create_foreign_key(
            "fk_master_data_sel_org_project_id",
            "project_master_data_selections",
            "org_projects",
            ["org_project_id"],
            ["id"],
            ondelete="CASCADE",
        )
    if "ck_master_data_sel_project_xor" not in mds_checks:
        bind.execute(sa.text(
            "UPDATE project_master_data_selections SET org_project_id = NULL "
            "WHERE project_id IS NOT NULL AND org_project_id IS NOT NULL"
        ))
        bind.execute(sa.text(
            "DELETE FROM project_master_data_selections "
            "WHERE project_id IS NULL AND org_project_id IS NULL"
        ))
        op.create_check_constraint(
            "ck_master_data_sel_project_xor",
            "project_master_data_selections",
            "(project_id IS NOT NULL AND org_project_id IS NULL) OR "
            "(project_id IS NULL AND org_project_id IS NOT NULL)",
        )
    if "ix_project_master_data_sel_org_project_id" not in mds_indexes:
        op.create_index(
            "ix_project_master_data_sel_org_project_id", "project_master_data_selections", ["org_project_id"]
        )

    # ── 9. project_opening_balance_selections: project_id nullable, add org_project_id
    op.alter_column(
        "project_opening_balance_selections", "project_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True
    )
    obs_cols = {c["name"] for c in inspector.get_columns("project_opening_balance_selections")}
    obs_indexes = {i["name"] for i in inspector.get_indexes("project_opening_balance_selections")}
    obs_fks = {fk["name"] for fk in inspector.get_foreign_keys("project_opening_balance_selections")}
    obs_checks = {ck["name"] for ck in inspector.get_check_constraints("project_opening_balance_selections")}
    if "org_project_id" not in obs_cols:
        op.add_column(
            "project_opening_balance_selections",
            sa.Column("org_project_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
    if "fk_opening_bal_sel_org_project_id" not in obs_fks:
        op.create_foreign_key(
            "fk_opening_bal_sel_org_project_id",
            "project_opening_balance_selections",
            "org_projects",
            ["org_project_id"],
            ["id"],
            ondelete="CASCADE",
        )
    if "ck_opening_bal_sel_project_xor" not in obs_checks:
        bind.execute(sa.text(
            "UPDATE project_opening_balance_selections SET org_project_id = NULL "
            "WHERE project_id IS NOT NULL AND org_project_id IS NOT NULL"
        ))
        bind.execute(sa.text(
            "DELETE FROM project_opening_balance_selections "
            "WHERE project_id IS NULL AND org_project_id IS NULL"
        ))
        op.create_check_constraint(
            "ck_opening_bal_sel_project_xor",
            "project_opening_balance_selections",
            "(project_id IS NOT NULL AND org_project_id IS NULL) OR "
            "(project_id IS NULL AND org_project_id IS NOT NULL)",
        )
    if "ix_project_opening_bal_sel_org_project_id" not in obs_indexes:
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
