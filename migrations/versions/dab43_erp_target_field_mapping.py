"""dab43: rename odoo_target to erp_target in item_field_profiles

Revision ID: dab43_erp_target_field_mapping
Revises: dab42_source_profile_stats
Create Date: 2026-07-28
"""

from alembic import op

revision = "dab43_erp_target_field_mapping"
down_revision = "dab42_source_profile_stats"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("item_field_profiles", "odoo_target", new_column_name="erp_target")


def downgrade() -> None:
    op.alter_column("item_field_profiles", "erp_target", new_column_name="odoo_target")
