"""add extra_instruction to application

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-07-16 12:00:00.000000

Application.extra_instruction — доп. инструкция владельца к LLM
при генерации. Сохраняется для переиспользования.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'n4o5p6q7r8s9'
down_revision: Union[str, Sequence[str], None] = 'm3n4o5p6q7r8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('application', sa.Column('extra_instruction', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('application', 'extra_instruction')
