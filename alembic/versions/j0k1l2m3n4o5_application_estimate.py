"""add estimate to application

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-07-06 12:00:00.000000

Application.estimate — оценка стоимости/сроков от LLM (фриланс, для владельца).
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'j0k1l2m3n4o5'
down_revision: str | Sequence[str] | None = 'i9j0k1l2m3n4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('application', sa.Column('estimate', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('application', 'estimate')
