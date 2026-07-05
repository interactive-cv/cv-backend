"""add session_id to link_hit

Revision ID: g7h8i9j0k1l2
Revises: f6g7h8i9j0k1
Create Date: 2026-07-05 14:00:00.000000

LinkHit.session_id — связь с chat_session для единого профиля посетителя.
Nullable: старые клики не имеют session_id.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'g7h8i9j0k1l2'
down_revision: Union[str, Sequence[str], None] = 'f6g7h8i9j0k1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'link_hit',
        sa.Column('session_id', sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        'fk_linkhit_session',
        'link_hit',
        'chat_session',
        ['session_id'],
        ['id'],
    )
    op.create_index('ix_linkhit_session', 'link_hit', ['session_id'])


def downgrade() -> None:
    op.drop_index('ix_linkhit_session', table_name='link_hit')
    op.drop_constraint('fk_linkhit_session', 'link_hit', type_='foreignkey')
    op.drop_column('link_hit', 'session_id')
