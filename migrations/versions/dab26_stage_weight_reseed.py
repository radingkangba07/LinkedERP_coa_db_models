"""add weight to workstream_stages and reseed with weighted pipeline stages

Revision ID: dab26_stage_weight_reseed
Revises: d6e7f8a9b0c1, dab16_extend_project_org_file
Create Date: 2026-07-15

Replaces the old 4-stage structure (ERP Select / Field Mapping / Validation /
Migration) with the weighted 6-stage pipeline:

  Upload Files                        30 %
  Type Mapping                        30 %
  Account Mapping: Low Confidence     10 %
  Account Mapping: Medium Confidence  10 %
  Account Mapping: Strong Confidence  10 %
  Preview & Export                    10 %

All existing stage rows are dropped and re-seeded.
Workstream current_stage is reset to "Upload Files".
Progress is now SUM(weight WHERE is_completed = true).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "dab26_stage_weight_reseed"
down_revision: tuple[str, str] = ("d6e7f8a9b0c1", "dab16_extend_project_org_file")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_STAGES: list[tuple[str, int, int]] = [
    ("Upload Files", 1, 30),
    ("Type Mapping", 2, 30),
    ("Account Mapping: Low Confidence", 3, 10),
    ("Account Mapping: Medium Confidence", 4, 10),
    ("Account Mapping: Strong Confidence", 5, 10),
    ("Preview & Export", 6, 10),
]


def upgrade() -> None:
    # 1. Widen name column to accommodate longer stage labels
    op.alter_column(
        "workstream_stages",
        "name",
        existing_type=sa.String(50),
        type_=sa.String(100),
        existing_nullable=False,
    )

    # 2. Add weight column (default 0 keeps existing rows valid during the operation)
    op.add_column(
        "workstream_stages",
        sa.Column("weight", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )

    # 3. Drop all existing stage rows — old pipeline is retired
    op.execute("DELETE FROM workstream_stages")

    # 4. Re-seed every workstream with the new 6 weighted stages
    for stage_name, seq, weight in _NEW_STAGES:
        op.execute(
            sa.text(
                """
                INSERT INTO workstream_stages (id, workstream_id, name, sequence, weight, is_completed)
                SELECT gen_random_uuid(), w.id, :name, :seq, :weight, false
                FROM workstreams w
                """
            ).bindparams(name=stage_name, seq=seq, weight=weight)
        )

    # 5. Reset current_stage on all workstreams to the first pipeline step
    op.execute(sa.text("UPDATE workstreams SET current_stage = 'Upload Files'"))


def downgrade() -> None:
    op.alter_column(
        "workstream_stages",
        "name",
        existing_type=sa.String(100),
        type_=sa.String(50),
        existing_nullable=False,
    )
    op.drop_column("workstream_stages", "weight")
    op.execute("DELETE FROM workstream_stages")

    _old_stages = [
        ("ERP Select", 1),
        ("Field Mapping", 2),
        ("Validation", 3),
        ("Migration", 4),
    ]
    for stage_name, seq in _old_stages:
        op.execute(
            sa.text(
                """
                INSERT INTO workstream_stages (id, workstream_id, name, sequence, is_completed)
                SELECT gen_random_uuid(), w.id, :name, :seq, false
                FROM workstreams w
                """
            ).bindparams(name=stage_name, seq=seq)
        )
    op.execute(sa.text("UPDATE workstreams SET current_stage = 'erp_select'"))
