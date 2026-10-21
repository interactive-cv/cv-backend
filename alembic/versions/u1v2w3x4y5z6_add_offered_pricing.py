"""application: мои условия отклика (цена, вилка, срок)

Revision ID: u1v2w3x4y5z6
Revises: t0u1v2w3x4y5
Create Date: 2026-10-13 16:00:00.000000

Разделение цен: budget/budget_max — цены ЗАКАЗЧИКА; offered_price —
моя цена отклика (FL/Kwork точная, Profi — низ вилки), offered_price_max —
верх вилки (Profi), my_term_days — срок отклика в днях (FL/Kwork).
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'u1v2w3x4y5z6'
down_revision: str | Sequence[str] | None = 't0u1v2w3x4y5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('application', sa.Column('offered_price', sa.Text(), nullable=True))
    op.add_column('application', sa.Column('offered_price_max', sa.Text(), nullable=True))
    op.add_column('application', sa.Column('my_term_days', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('application', 'my_term_days')
    op.drop_column('application', 'offered_price_max')
    op.drop_column('application', 'offered_price')
