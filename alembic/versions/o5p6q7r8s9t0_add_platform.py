"""add platform to application

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-07-24 12:00:00.000000

Application.platform — биржа-источник (None|"fl"|"kwork").
При kwork используется отдельный промпт, генерируется только отклик.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'o5p6q7r8s9t0'
down_revision: str | Sequence[str] | None = 'n4o5p6q7r8s9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('application', sa.Column('platform', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('application', 'platform')
