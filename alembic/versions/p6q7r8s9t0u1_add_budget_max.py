"""add budget_max to application

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
Create Date: 2026-08-15 14:00:00.000000

Application.budget_max — kwork «Допустимый» бюджет (верхняя граница вилки).
budget = «Желаемый бюджет» (нижняя граница).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'p6q7r8s9t0u1'
down_revision: Union[str, Sequence[str], None] = 'o5p6q7r8s9t0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('application', sa.Column('budget_max', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('application', 'budget_max')
