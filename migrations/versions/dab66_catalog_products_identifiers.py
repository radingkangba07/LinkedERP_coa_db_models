"""dab66: catalogue ERP configurations name the ERP products they serve (product id -> baseline
edition), and scope routes list the fields that can serve as import keys.

Revision ID: dab66
Revises: dab65
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "dab66"
down_revision: Union[str, Sequence[str], None] = "dab65"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ADD COLUMN does not fire the row-level guard triggers, so active and retired versions keep their rows.
    op.add_column(
        "catalog_erp_configs",
        sa.Column("products", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"),
                  nullable=False),
    )
    op.add_column(
        "catalog_scope_routes",
        sa.Column("identifier_fields", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"),
                  nullable=False),
    )


def downgrade() -> None:
    op.drop_column("catalog_scope_routes", "identifier_fields")
    op.drop_column("catalog_erp_configs", "products")
