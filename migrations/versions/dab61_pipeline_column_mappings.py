"""dab61: add target_fields, column_mappings, and column_mapping_history tables

Revision ID: dab61
Revises: dab60
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "dab61"
down_revision: Union[str, Sequence[str], None] = "dab60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # target_fields — ERP field catalogue, keyed by (erp_id, scope)
    # ------------------------------------------------------------------
    op.create_table(
        "target_fields",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("erp_id", sa.String(50), nullable=False),
        sa.Column("scope", sa.String(100), nullable=False),
        sa.Column("field_id", sa.String(255), nullable=False),
        sa.Column("label", sa.String(500), nullable=False),
        sa.Column("dtype", sa.String(50), nullable=False),
        sa.Column("relation", sa.String(255), nullable=True),
        sa.Column("required", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("read_only", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("identifier", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("source", sa.String(20), nullable=False, server_default="seed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("source IN ('seed','upload','mcp')", name="ck_target_fields_source"),
    )
    op.create_index(
        "uix_target_fields_erp_scope_field",
        "target_fields",
        ["erp_id", "scope", "field_id"],
        unique=True,
    )
    op.create_index("ix_target_fields_erp_scope", "target_fields", ["erp_id", "scope"])

    # ------------------------------------------------------------------
    # column_mappings — one row per (run_id, source_field)
    # ------------------------------------------------------------------
    op.create_table(
        "column_mappings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_field", sa.String(255), nullable=False),
        sa.Column("target_field_id", sa.String(255), nullable=True),
        sa.Column("target_field_label", sa.String(500), nullable=True),
        sa.Column("target_dtype", sa.String(50), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="no_safe_target"),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("mapping_source", sa.String(10), nullable=False, server_default="ai"),
        sa.Column("validation", sa.String(30), nullable=True),
        sa.Column("evidence", JSONB, nullable=True),
        sa.Column("confirmed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('suggested','review_required','confirmed','excluded','no_safe_target')",
            name="ck_column_mappings_status",
        ),
        sa.CheckConstraint(
            "mapping_source IN ('ai','user')",
            name="ck_column_mappings_source",
        ),
        sa.CheckConstraint(
            "validation IS NULL OR validation IN ('compatible','warning','format_conversion_required','incompatible')",
            name="ck_column_mappings_validation",
        ),
    )
    op.create_index(
        "uix_column_mappings_run_field",
        "column_mappings",
        ["run_id", "source_field"],
        unique=True,
    )
    op.create_index("ix_column_mappings_run_id", "column_mappings", ["run_id"])
    op.create_index("ix_column_mappings_run_status", "column_mappings", ["run_id", "status"])

    # ------------------------------------------------------------------
    # column_mapping_history — audit trail for user-confirmed changes
    # ------------------------------------------------------------------
    op.create_table(
        "column_mapping_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "mapping_id",
            UUID(as_uuid=True),
            sa.ForeignKey("column_mappings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("run_id", UUID(as_uuid=True), nullable=False),
        sa.Column("previous_target_field_id", sa.String(255), nullable=True),
        sa.Column("new_target_field_id", sa.String(255), nullable=True),
        sa.Column("previous_status", sa.String(30), nullable=True),
        sa.Column("new_status", sa.String(30), nullable=True),
        sa.Column("changed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("reason", sa.Text, nullable=True),
    )
    op.create_index("ix_col_mapping_history_mapping_id", "column_mapping_history", ["mapping_id"])
    op.create_index("ix_col_mapping_history_run_id", "column_mapping_history", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_col_mapping_history_run_id", table_name="column_mapping_history")
    op.drop_index("ix_col_mapping_history_mapping_id", table_name="column_mapping_history")
    op.drop_table("column_mapping_history")

    op.drop_index("ix_column_mappings_run_status", table_name="column_mappings")
    op.drop_index("ix_column_mappings_run_id", table_name="column_mappings")
    op.drop_index("uix_column_mappings_run_field", table_name="column_mappings")
    op.drop_table("column_mappings")

    op.drop_index("ix_target_fields_erp_scope", table_name="target_fields")
    op.drop_index("uix_target_fields_erp_scope_field", table_name="target_fields")
    op.drop_table("target_fields")
