"""add master_data_entities table and entity_id to workstreams

Revision ID: dab45_master_data_entity
Revises: dab44_project_display_code_table
Create Date: 2026-08-05

Adds a master_data_entities reference table seeded with the 9 supported
entities (chart_of_accounts plus the 8 master-data objects). Extends the
workstreams table with a nullable entity_id FK so each workstream can be
directly linked to its entity for org-level auditing and filtering.

Opening Balance workstreams leave entity_id NULL. The unique constraint on
(project_id, entity_id) enforces one workstream per entity per project;
PostgreSQL does not apply unique constraints to NULL values so multiple
NULL rows per project are permitted.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "dab45_master_data_entity"
down_revision: str = "dab44_project_display_code_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENTITIES = [
    ("chart_of_accounts", "Chart of Accounts", 1),
    ("customers", "Customers", 2),
    ("vendors", "Vendors", 3),
    ("items", "Items", 4),
    ("locations", "Locations", 5),
    ("contacts", "Contacts", 6),
    ("vehicles", "Vehicles", 7),
    ("equipment", "Equipment", 8),
    ("fixed_assets", "Fixed Assets", 9),
]


def upgrade() -> None:
    op.create_table(
        "master_data_entities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_master_data_entities_slug"),
    )

    op.execute(
        sa.text(
            "INSERT INTO master_data_entities (slug, name, display_order) VALUES "
            + ", ".join(f"('{slug}', '{name}', {order})" for slug, name, order in _ENTITIES)
        )
    )

    op.add_column(
        "workstreams",
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_workstreams_entity_id",
        "workstreams",
        "master_data_entities",
        ["entity_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_workstream_project_entity", "workstreams", ["project_id", "entity_id"]
    )
    op.create_index("ix_workstreams_entity_id", "workstreams", ["entity_id"])


def downgrade() -> None:
    op.drop_index("ix_workstreams_entity_id", table_name="workstreams")
    op.drop_constraint("uq_workstream_project_entity", "workstreams", type_="unique")
    op.drop_constraint("fk_workstreams_entity_id", "workstreams", type_="foreignkey")
    op.drop_column("workstreams", "entity_id")
    op.drop_table("master_data_entities")
