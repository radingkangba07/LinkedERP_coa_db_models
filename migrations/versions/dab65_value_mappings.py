"""dab65: add value_mappings and value_mapping_history tables

Revision ID: dab65
Revises: dab63
Create Date: 2026-09-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "dab65"
down_revision = "dab63"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "value_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_field", sa.String(255), nullable=False),
        # source_value is Text; uniqueness is enforced via md5(source_value) (see index below)
        # to avoid the PostgreSQL B-tree entry limit (~2704 bytes) that a composite index on
        # (run_id, source_field, source_value) would breach for multi-byte UTF-8 values.
        # NULL source values are not permitted. The ML service must represent a missing source
        # value as an empty string '' — agreed convention so that null and empty-string do not
        # collapse into the same unique row.
        sa.Column("source_value", sa.Text(), nullable=False),
        sa.Column("mapping_subtype", sa.String(20), nullable=False),
        sa.Column("records_count", sa.Integer(), nullable=True),
        sa.Column("records_pct", sa.Float(), nullable=True),
        sa.Column("target_value", sa.Text(), nullable=True),
        sa.Column("target_record_id", sa.String(255), nullable=True),
        sa.Column("transformation_type", sa.String(30), nullable=False),
        sa.Column("evidence_type", sa.String(30), nullable=True),
        sa.Column("evidence_source", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), server_default="unresolved", nullable=False),
        sa.Column("mapping_source", sa.String(20), server_default="ai", nullable=False),
        sa.Column("confirmed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "mapping_subtype IN ('allowed_value','related_record')",
            name="ck_value_mappings_mapping_subtype",
        ),
        sa.CheckConstraint(
            "transformation_type IN ('replace','replace_preserve','apply_default','normalise','no_legal_target')",
            name="ck_value_mappings_transformation_type",
        ),
        sa.CheckConstraint(
            "evidence_type IS NULL OR evidence_type IN ('exact_match','alias','coa_mapping','no_match','no_coa_entry','no_legal_target')",
            name="ck_value_mappings_evidence_type",
        ),
        sa.CheckConstraint(
            "status IN ('suggested','unresolved','confirmed','blocked','excluded')",
            name="ck_value_mappings_status",
        ),
        sa.CheckConstraint(
            "mapping_source IN ('ai','user','bookmark','coa_mapping')",
            name="ck_value_mappings_mapping_source",
        ),
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["pipeline_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_value_mappings_run_id", "value_mappings", ["run_id"])
    op.create_index("ix_value_mappings_run_field", "value_mappings", ["run_id", "source_field"])
    op.create_index("ix_value_mappings_run_status", "value_mappings", ["run_id", "status"])
    op.create_index("ix_value_mappings_run_subtype", "value_mappings", ["run_id", "mapping_subtype"])
    op.create_index(
        "uix_value_mappings_run_field_value",
        "value_mappings",
        ["run_id", "source_field", sa.text("md5(source_value)")],
        unique=True,
    )

    op.create_table(
        "value_mapping_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("mapping_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("changed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("previous_transformation_type", sa.String(30), nullable=True),
        sa.Column("new_transformation_type", sa.String(30), nullable=True),
        sa.Column("previous_target_value", sa.Text(), nullable=True),
        sa.Column("new_target_value", sa.Text(), nullable=True),
        sa.Column("previous_target_record_id", sa.String(255), nullable=True),
        sa.Column("new_target_record_id", sa.String(255), nullable=True),
        sa.Column("previous_status", sa.String(20), nullable=True),
        sa.Column("new_status", sa.String(20), nullable=True),
        sa.Column("previous_notes", sa.Text(), nullable=True),
        sa.Column("new_notes", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "previous_status IS NULL OR previous_status IN ('suggested','unresolved','confirmed','blocked','excluded')",
            name="ck_value_mapping_history_prev_status",
        ),
        sa.CheckConstraint(
            "new_status IS NULL OR new_status IN ('suggested','unresolved','confirmed','blocked','excluded')",
            name="ck_value_mapping_history_new_status",
        ),
        sa.CheckConstraint(
            "previous_transformation_type IS NULL OR previous_transformation_type IN ('replace','replace_preserve','apply_default','normalise','no_legal_target')",
            name="ck_value_mapping_history_prev_transformation_type",
        ),
        sa.CheckConstraint(
            "new_transformation_type IS NULL OR new_transformation_type IN ('replace','replace_preserve','apply_default','normalise','no_legal_target')",
            name="ck_value_mapping_history_new_transformation_type",
        ),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["mapping_id"], ["value_mappings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_value_mapping_history_mapping_id", "value_mapping_history", ["mapping_id"])
    op.create_index("ix_value_mapping_history_run_id", "value_mapping_history", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_value_mapping_history_run_id", table_name="value_mapping_history")
    op.drop_index("ix_value_mapping_history_mapping_id", table_name="value_mapping_history")
    op.drop_table("value_mapping_history")
    op.drop_index("uix_value_mappings_run_field_value", table_name="value_mappings")
    op.drop_index("ix_value_mappings_run_subtype", table_name="value_mappings")
    op.drop_index("ix_value_mappings_run_status", table_name="value_mappings")
    op.drop_index("ix_value_mappings_run_field", table_name="value_mappings")
    op.drop_index("ix_value_mappings_run_id", table_name="value_mappings")
    op.drop_table("value_mappings")
