"""add odoo_target to item_field_profiles for Odoo schema knowledge annotation

Revision ID: dab41_odoo_target
Revises: dab40_fields_processed
Create Date: 2026-07-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "dab41_odoo_target"
down_revision = "dab40_fields_processed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "item_field_profiles",
        sa.Column("odoo_target", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("item_field_profiles", "odoo_target")
