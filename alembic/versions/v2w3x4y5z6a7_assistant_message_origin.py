"""assistant_message: фаза диалога (prep — предпубликационное обсуждение)

Revision ID: v2w3x4y5z6a7
Revises: u1v2w3x4y5z6
Create Date: 2026-10-29 12:00:00.000000

Сообщения EditChat (подготовка отклика до публикации) сохраняются в тот же
тред ассистента с origin="prep". NULL у существующих строк — тред вкладки
«Диалог»; prep-сообщения всегда включаются в контекст LLM.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'v2w3x4y5z6a7'
down_revision: str | Sequence[str] | None = 'u1v2w3x4y5z6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('assistant_message', sa.Column('origin', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('assistant_message', 'origin')
