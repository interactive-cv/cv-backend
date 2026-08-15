"""add budget_max to application

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
Create Date: 2026-08-15 14:00:00.000000

Application.budget_max — kwork «Допустимый» бюджет (верхняя граница вилки).
budget = «Желаемый бюджет» (нижняя граница).
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'p6q7r8s9t0u1'
down_revision: str | Sequence[str] | None = 'o5p6q7r8s9t0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('application', sa.Column('budget_max', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('application', 'budget_max')
