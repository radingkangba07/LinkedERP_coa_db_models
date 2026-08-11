"""Relax XOR constraint on project_master_data_selections.

Allow a row to carry both project_id and org_project_id simultaneously,
so a non-COA scope created alongside a COA project can be stored as a
single row that links both entities. Replaces the strict XOR with an
AT-LEAST-ONE constraint.

Revision ID: dab52
Revises: dab51
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "dab52"
down_revision: Union[str, Sequence[str], None] = "dab51"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    constraints = {c["name"] for c in inspector.get_check_constraints("project_master_data_selections")}

    if "ck_master_data_sel_project_xor" in constraints:
        op.drop_constraint(
            "ck_master_data_sel_project_xor",
            "project_master_data_selections",
            type_="check",
        )

    if "ck_master_data_sel_at_least_one" not in constraints:
        op.create_check_constraint(
            "ck_master_data_sel_at_least_one",
            "project_master_data_selections",
            "(project_id IS NOT NULL OR org_project_id IS NOT NULL)",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    constraints = {c["name"] for c in inspector.get_check_constraints("project_master_data_selections")}

    if "ck_master_data_sel_at_least_one" in constraints:
        op.drop_constraint(
            "ck_master_data_sel_at_least_one",
            "project_master_data_selections",
            type_="check",
        )

    if "ck_master_data_sel_project_xor" not in constraints:
        op.create_check_constraint(
            "ck_master_data_sel_project_xor",
            "project_master_data_selections",
            "(project_id IS NOT NULL AND org_project_id IS NULL) OR "
            "(project_id IS NULL AND org_project_id IS NOT NULL)",
        )
