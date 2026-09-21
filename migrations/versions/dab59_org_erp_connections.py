"""dab59: add org_erp_connections table

Revision ID: dab59
Revises: dab58
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "dab59"
down_revision: Union[str, Sequence[str], None] = "dab57"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "org_erp_connections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("erp_id", sa.String(50), nullable=False),
        sa.Column("connection_role", sa.String(20), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("auth_strategy", sa.String(20), nullable=False),
        sa.Column("erp_config", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("consecutive_failures", sa.Integer, nullable=False, server_default="0"),
        sa.Column("health_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("catalogue_seeded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("erp_id IN ('odoo','netsuite','tally')", name="ck_org_erp_connections_erp_id"),
        sa.CheckConstraint("connection_role IN ('source','target')", name="ck_org_erp_connections_role"),
        sa.CheckConstraint(
            "auth_strategy IN ('api_key','tba','oauth2','bearer','tally_xml')",
            name="ck_org_erp_connections_auth_strategy",
        ),
        sa.CheckConstraint(
            "status IN ('active','broken','requires_reauth','tally_unreachable')",
            name="ck_org_erp_connections_status",
        ),
    )

    op.create_index("ix_org_erp_connections_org_id", "org_erp_connections", ["org_id"])

    # Unique: one label per org
    op.create_index(
        "uix_org_erp_connections_org_label",
        "org_erp_connections",
        ["org_id", "label"],
        unique=True,
    )

    # Partial unique: one active connection per org per erp per role
    op.create_index(
        "uix_org_erp_connections_active",
        "org_erp_connections",
        ["org_id", "erp_id", "connection_role"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("uix_org_erp_connections_active", table_name="org_erp_connections")
    op.drop_index("uix_org_erp_connections_org_label", table_name="org_erp_connections")
    op.drop_index("ix_org_erp_connections_org_id", table_name="org_erp_connections")
    op.drop_table("org_erp_connections")
