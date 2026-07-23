"""add semantic role inference columns to item_field_profiles

Revision ID: dab36_semantic_role
Revises: dab35_pattern_anomaly
Create Date: 2026-07-23

  item_field_profiles.semantic_role     — varchar(50): role classification
  item_field_profiles.confidence_score  — float: 0.0–1.0 derived from stats
  item_field_profiles.evidence          — text: reproducible evidence string
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "dab36_semantic_role"
down_revision: str = "dab35_pattern_anomaly"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("item_field_profiles", sa.Column("semantic_role", sa.String(50), nullable=True))
    op.add_column("item_field_profiles", sa.Column("confidence_score", sa.Float, nullable=True))
    op.add_column("item_field_profiles", sa.Column("evidence", sa.Text, nullable=True))
    op.create_index("ix_item_field_profiles_role", "item_field_profiles", ["semantic_role"])


def downgrade() -> None:
    op.drop_index("ix_item_field_profiles_role", table_name="item_field_profiles")
    op.drop_column("item_field_profiles", "evidence")
    op.drop_column("item_field_profiles", "confidence_score")
    op.drop_column("item_field_profiles", "semantic_role")
