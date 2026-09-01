"""dab55: add pipeline_runs and field_profiles; drop legacy source_profile schema;
add org_project_type_active index on project_files

Revision ID: dab55
Revises: dab53
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "dab55"
down_revision: Union[str, Sequence[str], None] = "dab53"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop legacy per-scope profiling schema — replaced by pipeline_runs + field_profiles.
    op.execute("DROP SCHEMA IF EXISTS source_profile CASCADE")

    op.create_table(
        "pipeline_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workstream_id", UUID(as_uuid=True), sa.ForeignKey("workstreams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("source_file_ref", sa.String(500), nullable=False),
        sa.Column("source_row_count", sa.Integer(), nullable=True),
        sa.Column("field_count", sa.Integer(), nullable=True),
        sa.Column("fields_processed", sa.Integer(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "scope IN ('items','customers','vendors','locations','contacts','vehicles','equipment','fixed_assets')",
            name="ck_pipeline_runs_scope",
        ),
        sa.CheckConstraint(
            "status IN ('pending','running','complete','failed','error')",
            name="ck_pipeline_runs_status",
        ),
    )
    op.create_index("ix_pipeline_runs_workstream_id", "pipeline_runs", ["workstream_id"])
    op.create_index("ix_pipeline_runs_org_id", "pipeline_runs", ["org_id"])
    op.create_index("ix_pipeline_runs_status", "pipeline_runs", ["status"])
    op.create_index("ix_pipeline_runs_scope", "pipeline_runs", ["scope"])
    op.create_index(
        "uix_pipeline_runs_workstream_scope_active",
        "pipeline_runs",
        ["workstream_id", "scope"],
        unique=True,
        postgresql_where=sa.text("status NOT IN ('complete','failed','error')"),
    )

    op.create_table(
        "field_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field_name", sa.String(255), nullable=False),
        sa.Column("detected_type", sa.String(50), nullable=True),
        sa.Column("format_detected", sa.String(20), nullable=True),
        sa.Column("user_override_type", sa.String(20), nullable=True),
        sa.Column("override_status", sa.String(20), nullable=True),
        sa.Column("overridden_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("overridden_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_count", sa.Integer(), nullable=True),
        sa.Column("null_count", sa.Integer(), nullable=True),
        sa.Column("distinct_count", sa.Integer(), nullable=True),
        sa.Column("cardinality", sa.String(20), nullable=True),
        sa.Column("duplicate_row_count", sa.Integer(), nullable=True),
        sa.Column("duplicate_group_count", sa.Integer(), nullable=True),
        sa.Column("invalid_count", sa.Integer(), nullable=True),
        sa.Column("reference_failures", sa.Integer(), nullable=True),
        sa.Column("is_enumeration_candidate", sa.Boolean(), nullable=True),
        sa.Column("pattern_anomalies", sa.Integer(), nullable=True),
        sa.Column("anomaly_count", sa.Integer(), nullable=True),
        sa.Column("semantic_role", sa.String(50), nullable=True),
        sa.Column("role_description", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(20), nullable=True),
        sa.Column("stats", JSONB, nullable=True),
        sa.Column("pattern_summary", JSONB, nullable=True),
        sa.Column("anomaly_examples", JSONB, nullable=True),
        sa.Column("enumeration_detail", JSONB, nullable=True),
        sa.Column("sample_values", JSONB, nullable=True),
        sa.Column("value_distribution", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("severity IN ('blocker','warning','review','clean')", name="ck_field_profiles_severity"),
        sa.CheckConstraint("cardinality IN ('near_empty','low','medium','high')", name="ck_field_profiles_cardinality"),
        sa.CheckConstraint(
            "detected_type IS NULL OR detected_type IN ('text','integer','decimal','date','boolean')",
            name="ck_field_profiles_detected_type",
        ),
        sa.CheckConstraint(
            "user_override_type IS NULL OR user_override_type IN ('text','integer','decimal','date','boolean')",
            name="ck_field_profiles_override_type",
        ),
        sa.CheckConstraint(
            "override_status IS NULL OR override_status IN ('pending','complete')",
            name="ck_field_profiles_override_status",
        ),
        sa.CheckConstraint(
            "semantic_role IS NULL OR semantic_role IN "
            "('identifier_candidate','display_name','descriptive_text','measure','value_list','timestamp','ambiguous')",
            name="ck_field_profiles_semantic_role",
        ),
    )
    op.create_index("ix_field_profiles_run_id", "field_profiles", ["run_id"])
    op.create_index("ix_field_profiles_run_field", "field_profiles", ["run_id", "field_name"])
    op.create_index("ix_field_profiles_run_severity", "field_profiles", ["run_id", "severity"])
    op.create_index("ix_field_profiles_run_override_status", "field_profiles", ["run_id", "override_status"])

    op.create_index(
        "ix_project_files_org_project_type_active",
        "project_files",
        ["org_project_id", "file_type"],
        postgresql_where=sa.text("is_active"),
    )


def downgrade() -> None:
    op.drop_index("ix_project_files_org_project_type_active", table_name="project_files")
    op.drop_index("ix_field_profiles_run_override_status", table_name="field_profiles")
    op.drop_index("ix_field_profiles_run_severity", table_name="field_profiles")
    op.drop_index("ix_field_profiles_run_field", table_name="field_profiles")
    op.drop_index("ix_field_profiles_run_id", table_name="field_profiles")
    op.drop_table("field_profiles")
    op.drop_index("uix_pipeline_runs_workstream_scope_active", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_scope", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_status", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_org_id", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_workstream_id", table_name="pipeline_runs")
    op.drop_table("pipeline_runs")
