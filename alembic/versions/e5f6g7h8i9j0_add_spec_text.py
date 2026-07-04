"""add spec_text to application (ТЗ заказа)

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-07-04 23:00:00.000000

spec_text — извлечённый текст ТЗ (из PDF или вставленный вручную).
Идёт в промпт генерации если заполнено.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5f6g7h8i9j0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6g7h8i9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('application', sa.Column('spec_text', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('application', 'spec_text')
