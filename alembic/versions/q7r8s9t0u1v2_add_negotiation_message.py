"""add negotiation_message table

Revision ID: q7r8s9t0u1v2
Revises: p6q7r8s9t0u1
Create Date: 2026-09-17 10:00:00.000000

Переговоры с заказчиком внутри карточки отклика: сообщения заказчика
(вставлены копипастом с площадки) и ответы владельца, с пометкой канала
(fl / telegram / email).
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'q7r8s9t0u1v2'
down_revision: str | Sequence[str] | None = 'p6q7r8s9t0u1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'negotiation_message',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column(
            'application_id',
            sa.Uuid(),
            sa.ForeignKey('application.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('role', sa.Text(), nullable=False),
        sa.Column('channel', sa.Text(), nullable=False, server_default='fl'),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        'ix_negotiation_message_application',
        'negotiation_message',
        ['application_id'],
    )


def downgrade() -> None:
    op.drop_index(
        'ix_negotiation_message_application', table_name='negotiation_message'
    )
    op.drop_table('negotiation_message')
