"""add assistant_message + application.draft_reply

Revision ID: r8s9t0u1v2w3
Revises: q7r8s9t0u1v2
Create Date: 2026-09-17 16:00:00.000000

Тред владельца с LLM-ассистентом по отклику (вопросы, тактика, подготовка
ответов заказчику) + автосохраняемый черновик ответа заказчику.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'r8s9t0u1v2w3'
down_revision: str | Sequence[str] | None = 'q7r8s9t0u1v2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'assistant_message',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column(
            'application_id',
            sa.Uuid(),
            sa.ForeignKey('application.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('role', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        'ix_assistant_message_application',
        'assistant_message',
        ['application_id'],
    )
    op.add_column('application', sa.Column('draft_reply', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('application', 'draft_reply')
    op.drop_index(
        'ix_assistant_message_application', table_name='assistant_message'
    )
    op.drop_table('assistant_message')
