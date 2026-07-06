"""merge phantom revision e1f2a3b4c5d6 into main migration chain

Revision ID: fix_merge_phantom_revision
Revises: dab16_extend_project_org_file, e1f2a3b4c5d6
Create Date: 2026-07-06

"""

from collections.abc import Sequence

revision: str = "fix_merge_phantom_revision"
down_revision: tuple = ("dab16_extend_project_org_file", "e1f2a3b4c5d6")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
