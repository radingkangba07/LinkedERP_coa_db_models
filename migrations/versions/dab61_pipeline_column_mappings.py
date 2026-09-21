"""dab61: add missing CHECK constraints to column-mapping tables

The target_fields, column_mappings, and column_mapping_history tables were
created by dab58 (since removed from the repo). This migration adds the
CHECK constraints that were omitted at that time:
  - ck_target_fields_scope     — prevents free-form scope strings on target_fields
  - ck_col_mapping_history_prev_status / ck_col_mapping_history_new_status
      — ensures the audit trail only records valid status values

Revision ID: dab61
Revises: dab60
"""

from typing import Sequence, Union

from alembic import op

revision: str = "dab61"
down_revision: Union[str, Sequence[str], None] = "dab60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_target_fields_scope",
        "target_fields",
        "scope IN ('items','customers','vendors','locations','contacts',"
        "'vehicles','equipment','fixed_assets')",
    )
    op.create_check_constraint(
        "ck_col_mapping_history_prev_status",
        "column_mapping_history",
        "previous_status IS NULL OR previous_status IN "
        "('suggested','review_required','confirmed','excluded','no_safe_target')",
    )
    op.create_check_constraint(
        "ck_col_mapping_history_new_status",
        "column_mapping_history",
        "new_status IS NULL OR new_status IN "
        "('suggested','review_required','confirmed','excluded','no_safe_target')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_col_mapping_history_new_status", "column_mapping_history", type_="check")
    op.drop_constraint("ck_col_mapping_history_prev_status", "column_mapping_history", type_="check")
    op.drop_constraint("ck_target_fields_scope", "target_fields", type_="check")
