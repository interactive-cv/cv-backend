"""company nullable (отклик без заказчика/компании)

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-07-04 22:00:00.000000

company теперь необязательное поле: фриланс-отклик может быть без заказчика
(или вакансия без компании). Существующие записи не затрагиваются.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e5f6g7h8i9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6g7h8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'application',
        'company',
        existing_type=sa.Text(),
        nullable=True,
    )


def downgrade() -> None:
    # При откате заполняем пустые company и делаем NOT NULL
    op.execute("UPDATE application SET company = '' WHERE company IS NULL")
    op.alter_column(
        'application',
        'company',
        existing_type=sa.Text(),
        nullable=False,
    )
