"""add invitations, coa_mapping_history, account_type_mappings, coa_embedding_store

Revision ID: b3f8a2c1d4e5
Revises: a1b2c3d4e5f6
Create Date: 2026-04-12 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "b3f8a2c1d4e5"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 2. Create invitations table
    op.create_table(
        "invitations",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), server_default="member", nullable=False),
        sa.Column("invited_by", sa.UUID(), nullable=False),
        sa.Column("token", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index(op.f("ix_invitations_org_id"), "invitations", ["org_id"], unique=False)
    op.create_index("ix_invitations_org_email", "invitations", ["org_id", "email"], unique=False)

    # 3. Create coa_mapping_history table
    op.create_table(
        "coa_mapping_history",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("coa_mapping_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("old_target_row_id", sa.UUID(), nullable=True),
        sa.Column("new_target_row_id", sa.UUID(), nullable=True),
        sa.Column("old_status", sa.String(length=20), nullable=True),
        sa.Column("new_status", sa.String(length=20), nullable=True),
        sa.Column("changed_by", sa.UUID(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["coa_mapping_id"], ["coa_mappings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_coa_mapping_history_mapping_id", "coa_mapping_history", ["coa_mapping_id"], unique=False)
    op.create_index("ix_coa_mapping_history_project_id", "coa_mapping_history", ["project_id"], unique=False)

    # 4. Create account_type_mappings table
    op.create_table(
        "account_type_mappings",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("mapping_file_id", sa.UUID(), nullable=True),
        sa.Column("source_account_type", sa.String(length=200), nullable=False),
        sa.Column("target_account_type", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mapping_file_id"], ["project_files.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_account_type_mappings_project_id", "account_type_mappings", ["project_id"], unique=False)

    # 5. Create coa_embedding_store table
    op.create_table(
        "coa_embedding_store",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("file_type", sa.String(length=50), nullable=False),
        sa.Column("source_account_type", sa.String(length=200), nullable=True),
        sa.Column("source_account_name", sa.String(length=500), nullable=True),
        sa.Column("target_account_type", sa.String(length=200), nullable=True),
        sa.Column("target_account_name", sa.String(length=500), nullable=True),
        sa.Column("normalized_name", sa.Text(), nullable=True),
        sa.Column("embedding_model", sa.String(length=100), nullable=False),
        sa.Column("embedding_version", sa.String(length=100), nullable=True),
        sa.Column("embedding_vector", Vector(1536), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_coa_embedding_store_project_id", "coa_embedding_store", ["project_id"], unique=False)
    op.create_index(
        "ix_coa_embedding_store_project_file_type",
        "coa_embedding_store",
        ["project_id", "file_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_coa_embedding_store_project_file_type", table_name="coa_embedding_store")
    op.drop_index("ix_coa_embedding_store_project_id", table_name="coa_embedding_store")
    op.drop_table("coa_embedding_store")

    op.drop_index("ix_account_type_mappings_project_id", table_name="account_type_mappings")
    op.drop_table("account_type_mappings")

    op.drop_index("ix_coa_mapping_history_project_id", table_name="coa_mapping_history")
    op.drop_index("ix_coa_mapping_history_mapping_id", table_name="coa_mapping_history")
    op.drop_table("coa_mapping_history")

    op.drop_index("ix_invitations_org_email", table_name="invitations")
    op.drop_index(op.f("ix_invitations_org_id"), table_name="invitations")
    op.drop_table("invitations")

    op.execute("DROP EXTENSION IF EXISTS vector")
