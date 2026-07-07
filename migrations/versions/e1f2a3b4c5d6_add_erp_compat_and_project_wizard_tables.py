"""add erp_compatibility_rules and project wizard tables

Revision ID: e1f2a3b4c5d6
Revises: a2b3c4d5e6f7
Create Date: 2026-07-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e1f2a3b4c5d6"
down_revision: str = "a2b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "erp_compatibility_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("source_product_id", sa.String(100), nullable=False),
        sa.Column("target_product_id", sa.String(100), nullable=False),
        sa.Column("connection_method_id", sa.String(100), nullable=True),
        sa.Column("is_compatible", sa.Boolean(), nullable=False),
        sa.Column("incompatibility_reason", sa.Text(), nullable=True),
    )
    op.create_index("ix_erp_compat_source", "erp_compatibility_rules", ["source_product_id"])
    op.create_index("ix_erp_compat_target", "erp_compatibility_rules", ["target_product_id"])

    op.create_table(
        "project_master_data_selections",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True, nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("data_type", sa.String(100), nullable=False),
        sa.Column("selected", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.create_index("ix_proj_master_data_project_id", "project_master_data_selections", ["project_id"])

    op.create_table(
        "project_opening_balance_selections",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True, nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_type", sa.String(100), nullable=False),
        sa.Column("include", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.create_index("ix_proj_opening_bal_project_id", "project_opening_balance_selections", ["project_id"])

    op.create_table(
        "project_wizard_fields",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("source_vendor_id", sa.String(100), nullable=True),
        sa.Column("target_vendor_id", sa.String(100), nullable=True),
        sa.Column("source_connection_method", sa.String(100), nullable=True),
        sa.Column("target_connection_method", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("project_wizard_fields")
    op.drop_index("ix_proj_opening_bal_project_id", table_name="project_opening_balance_selections")
    op.drop_table("project_opening_balance_selections")
    op.drop_index("ix_proj_master_data_project_id", table_name="project_master_data_selections")
    op.drop_table("project_master_data_selections")
    op.drop_index("ix_erp_compat_target", table_name="erp_compatibility_rules")
    op.drop_index("ix_erp_compat_source", table_name="erp_compatibility_rules")
    op.drop_table("erp_compatibility_rules")
