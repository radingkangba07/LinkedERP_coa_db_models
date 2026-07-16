"""no-op stub for phantom revision e1f2a3b4c5d6

Revision ID: e1f2a3b4c5d6
Revises: a2b3c4d5e6f7
Create Date: 2026-07-06

This revision was applied to the testing DB as a phantom before being
formally added to the migration chain. The actual table creation for
erp_compatibility_rules, project_master_data_selections,
project_opening_balance_selections, and project_wizard_fields is handled
by the parallel branch: b4c5d6e7f8a9 → c5d6e7f8a9b0 → d6e7f8a9b0c1.
"""

from collections.abc import Sequence

revision: str = "e1f2a3b4c5d6"
down_revision: str = "a2b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
