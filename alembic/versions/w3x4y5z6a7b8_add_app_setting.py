"""app_setting: системные настройки key-value (выбор LLM-модели, reasoning)

Revision ID: w3x4y5z6a7b8
Revises: v2w3x4y5z6a7
Create Date: 2026-11-16 12:00:00.000000

Новая таблица под служебные настройки админки (не редактируемые тексты):
  - llm_model — модель для всех вызовов z.ai (glm-5.3 / glm-5.3-flash);
  - llm_reasoning_effort — уровень рассуждений (low / high / max).
Записи создаются при первом изменении из админки; отсутствие записи =
поведение по умолчанию (env ZAI_MODEL + дефолт API). Обратимая, данные
не трогает.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'w3x4y5z6a7b8'
down_revision: str | Sequence[str] | None = 'v2w3x4y5z6a7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'app_setting',
        sa.Column('key', sa.Text(), nullable=False),
        sa.Column('value', sa.Text(), nullable=False, server_default=''),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('key'),
    )


def downgrade() -> None:
    op.drop_table('app_setting')
