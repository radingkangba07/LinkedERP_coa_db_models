"""dab59: add org_mapping_bookmarks table

Revision ID: dab59
Revises: dab58
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "dab59"
down_revision: Union[str, Sequence[str], None] = "dab58"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "org_mapping_bookmarks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("erp_id", sa.String(50), nullable=False),
        sa.Column("scope", sa.String(100), nullable=False),
        sa.Column("source_field", sa.String(255), nullable=False),
        sa.Column("mapping_type", sa.String(20), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("bookmarked_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("bookmarked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("mapping_type IN ('column','value','format')", name="ck_org_mapping_bookmarks_type"),
        sa.UniqueConstraint("org_id", "erp_id", "scope", "source_field", "mapping_type", name="uix_org_mapping_bookmarks"),
    )
    op.create_index(
        "ix_org_mapping_bookmarks_org_erp_scope_type",
        "org_mapping_bookmarks",
        ["org_id", "erp_id", "scope", "mapping_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_org_mapping_bookmarks_org_erp_scope_type", table_name="org_mapping_bookmarks")
    op.drop_table("org_mapping_bookmarks")
