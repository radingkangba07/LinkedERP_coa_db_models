"""merge companies into organizations

Revision ID: c4d5e6f7a8b9
Revises: b3f8a2c1d4e5
Create Date: 2026-04-13 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: str | None = "b3f8a2c1d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add slug and description columns to organizations
    op.add_column("organizations", sa.Column("slug", sa.String(length=100), nullable=True))
    op.add_column("organizations", sa.Column("description", sa.Text(), nullable=True))

    # 2. Data migration: copy slug/description from companies into organizations.
    #    For each company, find an org with the same name and update it;
    #    if no match, insert a new organization row.
    op.execute(
        """
        UPDATE organizations o
        SET slug = c.slug, description = c.description
        FROM companies c
        WHERE o.name = c.name
        """
    )
    op.execute(
        """
        INSERT INTO organizations (id, name, slug, description, created_at, updated_at)
        SELECT c.id, c.name, c.slug, c.description, c.created_at, c.updated_at
        FROM companies c
        WHERE NOT EXISTS (
            SELECT 1 FROM organizations o WHERE o.name = c.name
        )
        """
    )

    # 2b. Generate slugs for any organizations that didn't match a company
    op.execute(
        """
        UPDATE organizations
        SET slug = lower(regexp_replace(name, '[^a-zA-Z0-9]+', '-', 'g'))
        WHERE slug IS NULL
        """
    )

    # 3. Remap projects.company_id to point to corresponding organizations.id
    op.execute(
        """
        UPDATE projects p
        SET company_id = o.id
        FROM companies c
        JOIN organizations o ON o.slug = c.slug
        WHERE p.company_id = c.id
        """
    )

    # 4. Remap project_files.company_id similarly
    op.execute(
        """
        UPDATE project_files pf
        SET company_id = o.id
        FROM companies c
        JOIN organizations o ON o.slug = c.slug
        WHERE pf.company_id = c.id
        """
    )

    # 5. Drop old FK constraints and indexes on company_id
    # projects.company_id FK (unnamed from initial migration — Alembic convention name)
    op.drop_constraint("projects_company_id_fkey", "projects", type_="foreignkey")
    op.drop_index(op.f("ix_projects_company_id"), table_name="projects")

    # project_files.company_id FK (explicitly named)
    op.drop_constraint("fk_project_files_company_id", "project_files", type_="foreignkey")
    op.drop_index(op.f("ix_project_files_company_id"), table_name="project_files")

    # 6. Rename columns
    op.alter_column("projects", "company_id", new_column_name="org_id")
    op.alter_column("project_files", "company_id", new_column_name="org_id")

    # 7. Create new FK constraints and indexes on org_id
    op.create_foreign_key(
        "fk_projects_org_id",
        "projects",
        "organizations",
        ["org_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(op.f("ix_projects_org_id"), "projects", ["org_id"], unique=False)

    op.create_foreign_key(
        "fk_project_files_org_id",
        "project_files",
        "organizations",
        ["org_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(op.f("ix_project_files_org_id"), "project_files", ["org_id"], unique=False)

    # 8. Make organizations.slug not-null and add unique index
    op.alter_column("organizations", "slug", nullable=False)
    op.create_index(op.f("ix_organizations_slug"), "organizations", ["slug"], unique=True)

    # 9. Drop companies table
    op.drop_index(op.f("ix_companies_slug"), table_name="companies")
    op.drop_table("companies")


def downgrade() -> None:
    # 1. Recreate companies table
    op.create_table(
        "companies",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_companies_slug"), "companies", ["slug"], unique=True)

    # 2. Copy data from organizations back to companies (only rows that have a slug)
    op.execute(
        """
        INSERT INTO companies (id, slug, name, description, created_at, updated_at)
        SELECT gen_random_uuid(), slug, name, description, created_at, updated_at
        FROM organizations
        WHERE slug IS NOT NULL
        """
    )

    # 3. Drop new FK constraints and indexes on org_id
    op.drop_index(op.f("ix_project_files_org_id"), table_name="project_files")
    op.drop_constraint("fk_project_files_org_id", "project_files", type_="foreignkey")
    op.drop_index(op.f("ix_projects_org_id"), table_name="projects")
    op.drop_constraint("fk_projects_org_id", "projects", type_="foreignkey")

    # 4. Rename columns back
    op.alter_column("projects", "org_id", new_column_name="company_id")
    op.alter_column("project_files", "org_id", new_column_name="company_id")

    # 5. Remap company_id back to companies.id
    op.execute(
        """
        UPDATE projects p
        SET company_id = c.id
        FROM organizations o
        JOIN companies c ON c.slug = o.slug
        WHERE p.company_id = o.id
        """
    )
    op.execute(
        """
        UPDATE project_files pf
        SET company_id = c.id
        FROM organizations o
        JOIN companies c ON c.slug = o.slug
        WHERE pf.company_id = o.id
        """
    )

    # 6. Recreate old FK constraints and indexes
    op.create_foreign_key(
        "projects_company_id_fkey",
        "projects",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(op.f("ix_projects_company_id"), "projects", ["company_id"], unique=False)

    op.create_foreign_key(
        "fk_project_files_company_id",
        "project_files",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(op.f("ix_project_files_company_id"), "project_files", ["company_id"], unique=False)

    # 7. Drop slug and description from organizations
    op.drop_index(op.f("ix_organizations_slug"), table_name="organizations")
    op.drop_column("organizations", "description")
    op.drop_column("organizations", "slug")
