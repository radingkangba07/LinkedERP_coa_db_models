"""add erp_products table

Revision ID: dab17_add_erp_products_table
Revises: dab16_extend_project_org_file
Create Date: 2026-07-14

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "dab17_add_erp_products_table"
down_revision: str = "dab16_extend_project_org_file"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "erp_products",
        sa.Column("id", sa.String(150), primary_key=True, nullable=False),
        sa.Column("vendor", sa.String(200), nullable=False),
        sa.Column("product_name", sa.String(300), nullable=False),
        sa.Column(
            "connection_methods",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )
    op.create_index("ix_erp_products_vendor", "erp_products", ["vendor"])


def downgrade() -> None:
    op.drop_index("ix_erp_products_vendor", table_name="erp_products")
    op.drop_table("erp_products")
