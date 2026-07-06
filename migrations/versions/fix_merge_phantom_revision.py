"""stub for fix_merge_phantom_revision applied to testing DB

Revision ID: fix_merge_phantom_revision
Revises: dab14_workstream_stage
Create Date: 2026-07-06

"""

from collections.abc import Sequence

revision: str = "fix_merge_phantom_revision"
down_revision: str = "dab14_workstream_stage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
