"""change coa_mappings_suggestion.coa_mapping_id FK to ON DELETE SET NULL

Revision ID: d7e8f9a0b1c2
Revises: 61ab12d64988
Create Date: 2026-04-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d7e8f9a0b1c2"
down_revision: Union[str, Sequence[str], None] = "61ab12d64988"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


FK_NAME = "coa_mappings_suggestion_coa_mapping_id_fkey"
TABLE = "coa_mappings_suggestion"


def upgrade() -> None:
    """Recreate the FK so deleting a coa_mapping clears the link instead of deleting the suggestion."""
    op.drop_constraint(FK_NAME, TABLE, type_="foreignkey")
    op.create_foreign_key(
        FK_NAME,
        TABLE,
        "coa_mappings",
        ["coa_mapping_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Revert to ON DELETE CASCADE."""
    op.drop_constraint(FK_NAME, TABLE, type_="foreignkey")
    op.create_foreign_key(
        FK_NAME,
        TABLE,
        "coa_mappings",
        ["coa_mapping_id"],
        ["id"],
        ondelete="CASCADE",
    )
