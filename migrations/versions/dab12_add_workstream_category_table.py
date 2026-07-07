"""add workstream_category table

Revision ID: dab12_workstream_category
Revises: e1f2a3b4c5d6
Create Date: 2026-07-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "dab12_workstream_category"
down_revision: str = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workstream_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("display_code_prefix", sa.String(10), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_workstream_categories_slug", "workstream_categories", ["slug"], unique=True)

    # Seed initial categories
    op.execute(
        sa.text(
            "INSERT INTO workstream_categories (name, slug, display_code_prefix, display_order) VALUES "
            "('Master Data', 'master_data', 'MD', 1), "
            "('Opening Balances', 'opening_balances', 'OB', 2)"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_workstream_categories_slug", table_name="workstream_categories")
    op.drop_table("workstream_categories")
