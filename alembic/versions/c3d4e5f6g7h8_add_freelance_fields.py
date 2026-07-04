"""add freelance fields to application

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-07-04 20:00:00.000000

Расширение Application для фриланс-заказов (FL.ru и др.):
- kind: тип отклика (vacancy/freelance), default vacancy
- source_url: ссылка на вакансию/проект
- chat_url: ссылка на диалог с HR/заказчиком
- budget: бюджет заказа
- applicant_count: конкурс (сколько откликнулись)
- deadline: срок сдачи
- expected_term: ожидаемый срок найма/сотрудничества
- rating: внутренний рейтинг (1-5)

Все новые поля nullable — миграция не ломает существующие отклики.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6g7h8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6g7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Тип enum для kind. server_default='vacancy' — существующие отклики.
    op.execute("CREATE TYPE applicationkind AS ENUM ('vacancy', 'freelance')")
    op.add_column('application', sa.Column(
        'kind',
        sa.Enum(name='applicationkind'),
        nullable=False,
        server_default='vacancy',
    ))
    op.add_column('application', sa.Column('source_url', sa.Text(), nullable=True))
    op.add_column('application', sa.Column('chat_url', sa.Text(), nullable=True))
    op.add_column('application', sa.Column('budget', sa.Text(), nullable=True))
    op.add_column('application', sa.Column('applicant_count', sa.Integer(), nullable=True))
    op.add_column('application', sa.Column('deadline', sa.DateTime(timezone=True), nullable=True))
    op.add_column('application', sa.Column('expected_term', sa.Text(), nullable=True))
    op.add_column('application', sa.Column('rating', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('application', 'rating')
    op.drop_column('application', 'expected_term')
    op.drop_column('application', 'deadline')
    op.drop_column('application', 'applicant_count')
    op.drop_column('application', 'budget')
    op.drop_column('application', 'chat_url')
    op.drop_column('application', 'source_url')
    op.drop_column('application', 'kind')
    op.execute("DROP TYPE applicationkind")
