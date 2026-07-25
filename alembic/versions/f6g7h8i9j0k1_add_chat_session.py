"""add chat_session and chat_message tables

Revision ID: f6g7h8i9j0k1
Revises: e5f6g7h8i9j0
Create Date: 2026-07-05 12:00:00.000000

ChatSession + ChatMessage для продолжения диалога HR.
session_id (UUID) хранится в cookie, сообщения — в БД.
TTL: сессии старше 24ч удаляются lazy-cleanup.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'f6g7h8i9j0k1'
down_revision: str | Sequence[str] | None = 'e5f6g7h8i9j0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'chat_session',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('ip_hash', sa.Text(), nullable=True),
        sa.Column('visitor_name', sa.Text(), nullable=True),
        sa.Column('short_link_code', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('last_active_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['short_link_code'], ['short_link.code']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_chat_session_last_active', 'chat_session', ['last_active_at'])
    op.create_index('ix_chat_session_short_link', 'chat_session', ['short_link_code'])

    op.create_table(
        'chat_message',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('session_id', sa.Uuid(), nullable=False),
        sa.Column('role', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['session_id'], ['chat_session.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_chat_message_session', 'chat_message', ['session_id'])


def downgrade() -> None:
    op.drop_index('ix_chat_message_session', table_name='chat_message')
    op.drop_table('chat_message')
    op.drop_index('ix_chat_session_short_link', table_name='chat_session')
    op.drop_index('ix_chat_session_last_active', table_name='chat_session')
    op.drop_table('chat_session')
