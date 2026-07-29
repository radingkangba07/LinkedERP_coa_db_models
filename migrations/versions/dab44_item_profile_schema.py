"""dab44: move item profile tables to item_profile schema and add indexes

Revision ID: dab44_item_profile_schema
Revises: dab43_erp_target_field_mapping
Create Date: 2026-07-29
"""

from alembic import op

revision = "dab44_item_profile_schema"
down_revision = "dab43_erp_target_field_mapping"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS item_profile")

    # Move tables in FK-dependency order: parent first, then children.
    # Existing indexes and FK constraints follow the table automatically.
    op.execute("ALTER TABLE item_profile_runs SET SCHEMA item_profile")
    op.execute("ALTER TABLE item_profile_decisions SET SCHEMA item_profile")
    op.execute("ALTER TABLE item_field_profiles SET SCHEMA item_profile")
    op.execute("ALTER TABLE item_profile_audit SET SCHEMA item_profile")

    # -- Additional indexes (new; not present before this migration) --

    # item_profile_runs
    op.create_index(
        "ix_item_profile_runs_project_status",
        "item_profile_runs",
        ["project_id", "status"],
        schema="item_profile",
    )
    op.create_index(
        "ix_item_profile_runs_project_created",
        "item_profile_runs",
        ["project_id", "created_at"],
        schema="item_profile",
    )

    # item_field_profiles
    op.create_index(
        "ix_item_field_profiles_run_role",
        "item_field_profiles",
        ["run_id", "semantic_role"],
        schema="item_profile",
    )
    op.create_index(
        "ix_item_field_profiles_run_severity",
        "item_field_profiles",
        ["run_id", "severity"],
        schema="item_profile",
    )
    op.create_index(
        "ix_item_field_profiles_stats_gin",
        "item_field_profiles",
        ["stats"],
        schema="item_profile",
        postgresql_using="gin",
    )

    # item_profile_decisions
    op.create_index(
        "ix_item_profile_decisions_run_status",
        "item_profile_decisions",
        ["run_id", "status"],
        schema="item_profile",
    )

    # item_profile_audit
    op.create_index(
        "ix_item_profile_audit_changed_by",
        "item_profile_audit",
        ["changed_by"],
        schema="item_profile",
    )


def downgrade() -> None:
    # Drop new indexes first
    op.drop_index("ix_item_profile_audit_changed_by", table_name="item_profile_audit", schema="item_profile")
    op.drop_index("ix_item_profile_decisions_run_status", table_name="item_profile_decisions", schema="item_profile")
    op.drop_index("ix_item_field_profiles_stats_gin", table_name="item_field_profiles", schema="item_profile")
    op.drop_index("ix_item_field_profiles_run_severity", table_name="item_field_profiles", schema="item_profile")
    op.drop_index("ix_item_field_profiles_run_role", table_name="item_field_profiles", schema="item_profile")
    op.drop_index("ix_item_profile_runs_project_created", table_name="item_profile_runs", schema="item_profile")
    op.drop_index("ix_item_profile_runs_project_status", table_name="item_profile_runs", schema="item_profile")

    # Move tables back to public schema (reverse order: children first)
    op.execute("ALTER TABLE item_profile.item_profile_audit SET SCHEMA public")
    op.execute("ALTER TABLE item_profile.item_field_profiles SET SCHEMA public")
    op.execute("ALTER TABLE item_profile.item_profile_decisions SET SCHEMA public")
    op.execute("ALTER TABLE item_profile.item_profile_runs SET SCHEMA public")

    op.execute("DROP SCHEMA IF EXISTS item_profile")
