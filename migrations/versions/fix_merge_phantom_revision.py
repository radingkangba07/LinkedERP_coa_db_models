"""stub for fix_merge_phantom_revision applied to testing DB

Revision ID: fix_merge_phantom_revision
Revises: dab15_workstream_status_log
Create Date: 2026-07-06

"""

from collections.abc import Sequence

revision: str = "fix_merge_phantom_revision"
down_revision: str = "dab15_workstream_status_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
