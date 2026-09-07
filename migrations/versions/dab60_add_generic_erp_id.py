"""dab60: allow generic erp_id on org_erp_connections

Revision ID: dab60
Revises: dab59
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "dab60"
down_revision: Union[str, Sequence[str], None] = "dab59"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_org_erp_connections_erp_id", "org_erp_connections")
    op.create_check_constraint(
        "ck_org_erp_connections_erp_id",
        "org_erp_connections",
        "erp_id IN ('odoo','netsuite','tally','generic')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_org_erp_connections_erp_id", "org_erp_connections")
    op.create_check_constraint(
        "ck_org_erp_connections_erp_id",
        "org_erp_connections",
        "erp_id IN ('odoo','netsuite','tally')",
    )
