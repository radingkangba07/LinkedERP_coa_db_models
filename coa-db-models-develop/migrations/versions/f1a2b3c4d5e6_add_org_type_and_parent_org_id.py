"""add org_type and parent_org_id to organizations

Revision ID: f1a2b3c4d5e6
Revises: e8f9a0b1c2d3
Create Date: 2026-05-05 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "e8f9a0b1c2d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add org_type — DEFAULT 'employer' backfills all existing rows instantly
    op.add_column(
        "organizations",
        sa.Column("org_type", sa.String(length=20), nullable=False, server_default="employer"),
    )
    op.create_check_constraint(
        "chk_organizations_org_type",
        "organizations",
        "org_type IN ('employer', 'client')",
    )

    # 2. Add parent_org_id — self-referential FK, RESTRICT so deleting an employer
    #    with active client orgs is blocked until clients are removed first
    op.add_column(
        "organizations",
        sa.Column("parent_org_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_organizations_parent_org_id",
        "organizations",
        "organizations",
        ["parent_org_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # 3. Consistency constraint: employer ↔ no parent, client ↔ must have parent
    op.create_check_constraint(
        "chk_org_parent_consistency",
        "organizations",
        "(org_type = 'employer' AND parent_org_id IS NULL) OR "
        "(org_type = 'client' AND parent_org_id IS NOT NULL)",
    )

    # 4. Index for fast "give me all clients of employer X" lookups
    op.create_index("ix_organizations_parent_org_id", "organizations", ["parent_org_id"])

    # 5. Replace global name uniqueness with partial indexes scoped by org_type
    op.drop_constraint("organizations_name_key", "organizations", type_="unique")
    op.execute(
        "CREATE UNIQUE INDEX uq_org_name_employer ON organizations (name) WHERE org_type = 'employer'"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_org_name_client ON organizations (name, parent_org_id) WHERE org_type = 'client'"
    )

    # 6. Replace global slug uniqueness with partial indexes scoped by org_type
    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.execute(
        "CREATE UNIQUE INDEX uq_org_slug_employer ON organizations (slug) WHERE org_type = 'employer'"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_org_slug_client ON organizations (slug, parent_org_id) WHERE org_type = 'client'"
    )


def downgrade() -> None:
    # Restore global slug unique index
    op.execute("DROP INDEX IF EXISTS uq_org_slug_client")
    op.execute("DROP INDEX IF EXISTS uq_org_slug_employer")
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)

    # Restore global name unique constraint
    op.execute("DROP INDEX IF EXISTS uq_org_name_client")
    op.execute("DROP INDEX IF EXISTS uq_org_name_employer")
    op.create_unique_constraint("organizations_name_key", "organizations", ["name"])

    op.drop_index("ix_organizations_parent_org_id", table_name="organizations")
    op.drop_constraint("chk_org_parent_consistency", "organizations", type_="check")
    op.drop_constraint("fk_organizations_parent_org_id", "organizations", type_="foreignkey")
    op.drop_column("organizations", "parent_org_id")
    op.drop_constraint("chk_organizations_org_type", "organizations", type_="check")
    op.drop_column("organizations", "org_type")
