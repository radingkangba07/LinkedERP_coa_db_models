"""entity_packs and field_decisions tables

Revision ID: dab47_entity_packs_field_decisions
Revises: dab45_master_data_entity
Create Date: 2026-08-06

entity_packs — profiler output, one JSONB document per workstream run.
  Write-once. Re-profile inserts a new row; the old row flips to
  is_current=false. A partial unique index enforces at most one
  is_current=true row per workstream.

field_decisions — human decisions on profiled fields.
  Append-only. Supersede by setting is_active=false on the prior row for
  the same (workstream_id, field_id) before inserting the replacement.
  Decisions survive a re-profile; the new entity_pack row does not touch
  this table.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "dab47_packs_and_decisions"
down_revision: str = "dab45_master_data_entity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "entity_packs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("workstream_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pack", postgresql.JSONB(), nullable=False),
        sa.Column("schema_version", sa.String(50), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["workstream_id"], ["workstreams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_file_id"], ["project_files.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_entity_packs_workstream_id", "entity_packs", ["workstream_id"])
    op.create_index("ix_entity_packs_workstream_current", "entity_packs", ["workstream_id", "is_current"])
    op.create_index(
        "uq_entity_packs_workstream_current",
        "entity_packs",
        ["workstream_id"],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
    )

    op.create_table(
        "field_decisions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("workstream_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_id", sa.String(100), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("target_field_id", sa.String(255), nullable=True),
        sa.Column("previous_target_id", sa.String(255), nullable=True),
        sa.Column("decision_source", sa.String(20), server_default=sa.text("'user'"), nullable=False),
        sa.Column("approval_context", postgresql.JSONB(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("decided_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["workstream_id"], ["workstreams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_field_decisions_workstream_id", "field_decisions", ["workstream_id"])
    op.create_index(
        "ix_field_decisions_workstream_field_active",
        "field_decisions",
        ["workstream_id", "field_id", "is_active"],
    )


def downgrade() -> None:
    op.drop_index("ix_field_decisions_workstream_field_active", table_name="field_decisions")
    op.drop_index("ix_field_decisions_workstream_id", table_name="field_decisions")
    op.drop_table("field_decisions")

    op.drop_index("uq_entity_packs_workstream_current", table_name="entity_packs")
    op.drop_index("ix_entity_packs_workstream_current", table_name="entity_packs")
    op.drop_index("ix_entity_packs_workstream_id", table_name="entity_packs")
    op.drop_table("entity_packs")
