"""add pattern detection and anomaly columns

Revision ID: dab35_pattern_anomaly
Revises: dab34_field_stats_cols
Create Date: 2026-07-23

  item_field_profiles.pattern_summary    — JSONB: dominant pattern + variants
  item_field_profiles.anomaly_count      — integer count of non-conforming values
  item_field_profiles.anomaly_examples   — JSONB: up to 10 sample anomalous values
  item_profile_runs.duplicate_summary    — JSONB: duplicate group stats
  item_profile_runs.cross_subsidiary_summary — JSONB: cross-subsidiary split stats
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "dab35_pattern_anomaly"
down_revision: str = "dab34_field_stats_cols"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # item_field_profiles — pattern detection
    op.add_column("item_field_profiles", sa.Column("pattern_summary", JSONB, nullable=True))
    op.add_column("item_field_profiles", sa.Column("anomaly_count", sa.Integer, nullable=True))
    op.add_column("item_field_profiles", sa.Column("anomaly_examples", JSONB, nullable=True))

    # item_profile_runs — run-level anomaly summaries
    op.add_column("item_profile_runs", sa.Column("duplicate_summary", JSONB, nullable=True))
    op.add_column("item_profile_runs", sa.Column("cross_subsidiary_summary", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("item_profile_runs", "cross_subsidiary_summary")
    op.drop_column("item_profile_runs", "duplicate_summary")
    op.drop_column("item_field_profiles", "anomaly_examples")
    op.drop_column("item_field_profiles", "anomaly_count")
    op.drop_column("item_field_profiles", "pattern_summary")
