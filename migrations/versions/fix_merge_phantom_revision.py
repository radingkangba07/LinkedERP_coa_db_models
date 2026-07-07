"""no-op stub acknowledging phantom revision applied to testing DB

Revision ID: fix_merge_phantom_revision
Revises: e1f2a3b4c5d6
Create Date: 2026-07-07

"""

from collections.abc import Sequence

revision: str = "fix_merge_phantom_revision"
down_revision: str = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
