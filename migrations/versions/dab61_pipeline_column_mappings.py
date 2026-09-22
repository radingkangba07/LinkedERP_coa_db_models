"""dab61: add missing CHECK constraints to column-mapping tables

The target_fields, column_mappings, and column_mapping_history tables were
created by dab58 on the testing/fresh-CI path. On demo the dab58 revision was
replaced by a no-op merge point (dab58_merge_demo_develop), so those tables do
not exist there. This migration is therefore idempotent:

  - If the tables are absent (demo DB): create all three tables with every
    constraint and index inline, matching the dab58 DDL plus the three
    constraints added here.
  - If the tables are present (testing / fresh CI after dab58): add only the
    three CHECK constraints that dab58 omitted:
      - ck_target_fields_scope
      - ck_col_mapping_history_prev_status
      - ck_col_mapping_history_new_status

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

_SCOPE_CHECK = (
    "scope IN ('items','customers','vendors','locations','contacts',"
    "'vehicles','equipment','fixed_assets')"
)
_STATUS_VALUES = "('suggested','review_required','confirmed','excluded','no_safe_target')"
_PREV_STATUS_CHECK = f"previous_status IS NULL OR previous_status IN {_STATUS_VALUES}"
_NEW_STATUS_CHECK = f"new_status IS NULL OR new_status IN {_STATUS_VALUES}"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("target_fields"):
        # Demo path: tables were never created — build full schema with all constraints inline.
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
            sa.Column("source", sa.String(20), nullable=False, server_default=sa.text("'seed'")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint("source IN ('seed','upload','mcp')", name="ck_target_fields_source"),
            sa.CheckConstraint(_SCOPE_CHECK, name="ck_target_fields_scope"),
            sa.UniqueConstraint("erp_id", "scope", "field_id", name="uix_target_fields_erp_scope_field"),
        )
        op.create_index("ix_target_fields_erp_scope", "target_fields", ["erp_id", "scope"])

        op.create_table(
            "column_mappings",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_field", sa.String(255), nullable=False),
            sa.Column("target_field_id", sa.String(255), nullable=True),
            sa.Column("target_field_label", sa.String(500), nullable=True),
            sa.Column("target_dtype", sa.String(50), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'no_safe_target'")),
            sa.Column("confidence", sa.Float, nullable=True),
            sa.Column("mapping_source", sa.String(10), nullable=False, server_default=sa.text("'ai'")),
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
            sa.CheckConstraint("mapping_source IN ('ai','user')", name="ck_column_mappings_source"),
            sa.CheckConstraint(
                "validation IS NULL OR validation IN "
                "('compatible','warning','format_conversion_required','incompatible')",
                name="ck_column_mappings_validation",
            ),
            sa.UniqueConstraint("run_id", "source_field", name="uix_column_mappings_run_field"),
        )
        op.create_index("ix_column_mappings_run_id", "column_mappings", ["run_id"])
        op.create_index("ix_column_mappings_run_status", "column_mappings", ["run_id", "status"])

        op.create_table(
            "column_mapping_history",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("mapping_id", UUID(as_uuid=True), sa.ForeignKey("column_mappings.id", ondelete="CASCADE"), nullable=False),
            sa.Column("run_id", UUID(as_uuid=True), nullable=False),
            sa.Column("previous_target_field_id", sa.String(255), nullable=True),
            sa.Column("new_target_field_id", sa.String(255), nullable=True),
            sa.Column("previous_status", sa.String(30), nullable=True),
            sa.Column("new_status", sa.String(30), nullable=True),
            sa.Column("changed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("reason", sa.Text, nullable=True),
            sa.CheckConstraint(_PREV_STATUS_CHECK, name="ck_col_mapping_history_prev_status"),
            sa.CheckConstraint(_NEW_STATUS_CHECK, name="ck_col_mapping_history_new_status"),
        )
        op.create_index("ix_col_mapping_history_mapping_id", "column_mapping_history", ["mapping_id"])
        op.create_index("ix_col_mapping_history_run_id", "column_mapping_history", ["run_id"])

    else:
        # Testing / fresh-CI path: dab58 already created the tables — add only the missing constraints.
        op.create_check_constraint("ck_target_fields_scope", "target_fields", _SCOPE_CHECK)
        op.create_check_constraint("ck_col_mapping_history_prev_status", "column_mapping_history", _PREV_STATUS_CHECK)
        op.create_check_constraint("ck_col_mapping_history_new_status", "column_mapping_history", _NEW_STATUS_CHECK)


def downgrade() -> None:
    # Always drop the three CHECK constraints added by this migration.
    op.drop_constraint("ck_col_mapping_history_new_status", "column_mapping_history", type_="check")
    op.drop_constraint("ck_col_mapping_history_prev_status", "column_mapping_history", type_="check")
    op.drop_constraint("ck_target_fields_scope", "target_fields", type_="check")

    # On the demo path this migration also created the tables (dab58 was a no-op merge there).
    # Detect the demo path by checking whether the demo-only merge revision exists in the
    # script directory — it is absent on testing and fresh-CI branches.
    # On the testing path dab58 owns the table drops and will handle them on its own downgrade.
    _tables_created_here = False
    try:
        op.get_context().script.get_revision("dab58_merge_demo_develop")
        _tables_created_here = True
    except Exception:
        pass

    if _tables_created_here:
        op.drop_index("ix_col_mapping_history_run_id", table_name="column_mapping_history")
        op.drop_index("ix_col_mapping_history_mapping_id", table_name="column_mapping_history")
        op.drop_table("column_mapping_history")

        op.drop_index("ix_column_mappings_run_status", table_name="column_mappings")
        op.drop_index("ix_column_mappings_run_id", table_name="column_mappings")
        op.drop_table("column_mappings")

        op.drop_index("ix_target_fields_erp_scope", table_name="target_fields")
        op.drop_table("target_fields")
