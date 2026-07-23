"""add source_file_ref to runs; add severity and cardinality to field profiles

Revision ID: dab34_field_stats_cols
Revises: dab33_add_field_count_to_run
Create Date: 2026-07-23

  item_profile_runs.source_file_ref  — R2/S3 key of the ingested file so the
                                       stats consumer can re-download it
  item_field_profiles.severity       — blocker / warning / ok
  item_field_profiles.cardinality    — low / medium / high
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "dab34_field_stats_cols"
down_revision: str = "dab33_add_field_count_to_run"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "item_profile_runs",
        sa.Column("source_file_ref", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "item_field_profiles",
        sa.Column("severity", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "item_field_profiles",
        sa.Column("cardinality", sa.String(length=10), nullable=True),
    )
    op.create_index("ix_item_field_profiles_severity", "item_field_profiles", ["severity"])


def downgrade() -> None:
    op.drop_index("ix_item_field_profiles_severity", table_name="item_field_profiles")
    op.drop_column("item_field_profiles", "cardinality")
    op.drop_column("item_field_profiles", "severity")
    op.drop_column("item_profile_runs", "source_file_ref")
