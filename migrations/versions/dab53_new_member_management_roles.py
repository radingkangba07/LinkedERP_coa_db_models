"""dab53: new member management roles and permission model

Backfills existing role/permission values to the new model, then adds
CheckConstraints to enforce the valid set going forward.

Org roles:    owner/member -> admin/viewer  (3-role: admin, modifier, viewer)
Project perms: admin/approver -> owner/editor (3-role: owner, editor, viewer)

Revision ID: dab53
Revises: dab52
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "dab53"
down_revision: Union[str, Sequence[str], None] = "dab52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- 1. Backfill org roles before constraints are added ---
    op.execute("UPDATE organization_members SET role = 'admin' WHERE role = 'owner'")
    op.execute("UPDATE organization_members SET role = 'viewer' WHERE role = 'member'")
    op.execute("UPDATE organization_invitations SET role = 'admin' WHERE role = 'owner'")
    op.execute("UPDATE organization_invitations SET role = 'viewer' WHERE role = 'member'")

    # --- 2. Backfill project permissions before constraints are added ---
    op.execute("UPDATE project_access SET permission = 'owner' WHERE permission = 'admin'")
    op.execute("UPDATE project_access SET permission = 'editor' WHERE permission = 'approver'")
    op.execute("UPDATE org_project_access SET permission = 'owner' WHERE permission = 'admin'")
    op.execute("UPDATE org_project_access SET permission = 'editor' WHERE permission = 'approver'")

    # --- 3. Add CheckConstraints (idempotent) ---
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    member_constraints = {c["name"] for c in inspector.get_check_constraints("organization_members")}
    if "chk_org_member_role" not in member_constraints:
        op.create_check_constraint(
            "chk_org_member_role",
            "organization_members",
            "role IN ('admin', 'modifier', 'viewer')",
        )

    invitation_constraints = {c["name"] for c in inspector.get_check_constraints("organization_invitations")}
    if "chk_org_invitation_role" not in invitation_constraints:
        op.create_check_constraint(
            "chk_org_invitation_role",
            "organization_invitations",
            "role IN ('admin', 'modifier', 'viewer')",
        )

    project_access_constraints = {c["name"] for c in inspector.get_check_constraints("project_access")}
    if "chk_project_access_permission" not in project_access_constraints:
        op.create_check_constraint(
            "chk_project_access_permission",
            "project_access",
            "permission IN ('owner', 'editor', 'viewer')",
        )

    org_project_access_constraints = {c["name"] for c in inspector.get_check_constraints("org_project_access")}
    if "chk_org_project_access_permission" not in org_project_access_constraints:
        op.create_check_constraint(
            "chk_org_project_access_permission",
            "org_project_access",
            "permission IN ('owner', 'editor', 'viewer')",
        )


def downgrade() -> None:
    # --- 1. Drop CheckConstraints (idempotent) ---
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    member_constraints = {c["name"] for c in inspector.get_check_constraints("organization_members")}
    if "chk_org_member_role" in member_constraints:
        op.drop_constraint("chk_org_member_role", "organization_members", type_="check")

    invitation_constraints = {c["name"] for c in inspector.get_check_constraints("organization_invitations")}
    if "chk_org_invitation_role" in invitation_constraints:
        op.drop_constraint("chk_org_invitation_role", "organization_invitations", type_="check")

    project_access_constraints = {c["name"] for c in inspector.get_check_constraints("project_access")}
    if "chk_project_access_permission" in project_access_constraints:
        op.drop_constraint("chk_project_access_permission", "project_access", type_="check")

    org_project_access_constraints = {c["name"] for c in inspector.get_check_constraints("org_project_access")}
    if "chk_org_project_access_permission" in org_project_access_constraints:
        op.drop_constraint("chk_org_project_access_permission", "org_project_access", type_="check")

    # --- 2. Reverse the backfill ---
    op.execute("UPDATE organization_members SET role = 'owner' WHERE role = 'admin'")
    op.execute("UPDATE organization_members SET role = 'member' WHERE role IN ('modifier', 'viewer')")
    op.execute("UPDATE organization_invitations SET role = 'owner' WHERE role = 'admin'")
    op.execute("UPDATE organization_invitations SET role = 'member' WHERE role IN ('modifier', 'viewer')")

    op.execute("UPDATE project_access SET permission = 'admin' WHERE permission = 'owner'")
    op.execute("UPDATE project_access SET permission = 'approver' WHERE permission = 'editor'")
    op.execute("UPDATE org_project_access SET permission = 'admin' WHERE permission = 'owner'")
    op.execute("UPDATE org_project_access SET permission = 'approver' WHERE permission = 'editor'")
