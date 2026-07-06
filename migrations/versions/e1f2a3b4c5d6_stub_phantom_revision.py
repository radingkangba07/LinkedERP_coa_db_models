"""stub for phantom revision applied to testing DB but never committed to repo

Revision ID: e1f2a3b4c5d6
Revises: a2b3c4d5e6f7
Create Date: 2026-07-06

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
