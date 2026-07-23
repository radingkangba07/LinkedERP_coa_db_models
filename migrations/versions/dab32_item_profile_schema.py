"""add item profile tables for DAB-32

Revision ID: dab32_item_profile_schema
Revises: dab26_stage_weight_reseed
Create Date: 2026-07-23

Creates four tables to support item data profiling and field-level
decision tracking:

  item_profile_runs        — one row per profiling job invocation
  item_field_profiles      — per-field statistical analysis results
  item_profile_decisions   — human / AI action decisions per field
  item_profile_audit       — immutable audit trail for decision changes
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "dab32_item_profile_schema"
down_revision: str = "dab26_stage_weight_reseed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "item_profile_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("source_row_count", sa.Integer(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_item_profile_runs_project_id", "item_profile_runs", ["project_id"])
    op.create_index("ix_item_profile_runs_status", "item_profile_runs", ["status"])

    op.create_table(
        "item_field_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_name", sa.String(length=255), nullable=False),
        sa.Column("detected_type", sa.String(length=50), server_default="string", nullable=False),
        sa.Column("total_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("null_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("distinct_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("sample_values", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("stats", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["item_profile_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "field_name", name="uq_field_profile_run_field"),
    )
    op.create_index("ix_item_field_profiles_run_id", "item_field_profiles", ["run_id"])

    op.create_table(
        "item_profile_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_name", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=20), server_default="review", nullable=False),
        sa.Column("target_field", sa.String(length=255), nullable=True),
        sa.Column("transformation_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("decided_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["item_profile_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "field_name", name="uq_decision_run_field"),
    )
    op.create_index("ix_item_profile_decisions_run_id", "item_profile_decisions", ["run_id"])
    op.create_index("ix_item_profile_decisions_decided_by", "item_profile_decisions", ["decided_by"])

    op.create_table(
        "item_profile_audit",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("decision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("changed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("previous_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_state", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["decision_id"], ["item_profile_decisions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_item_profile_audit_decision_id", "item_profile_audit", ["decision_id"])


def downgrade() -> None:
    op.drop_table("item_profile_audit")
    op.drop_table("item_profile_decisions")
    op.drop_table("item_field_profiles")
    op.drop_table("item_profile_runs")
