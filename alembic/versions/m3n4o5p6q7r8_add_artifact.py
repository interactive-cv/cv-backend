"""add artifact table

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-07-13 12:00:00.000000

Artifact — файл-артефакт конкурсного отклика (APK, видео, и т.д.).
Публичная ссылка /dl/{code}. Аналитика скачиваний.
Каскадное удаление при удалении отклика (ondelete CASCADE на FK).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.types import Uuid

from alembic import op

revision: str = 'm3n4o5p6q7r8'
down_revision: str | Sequence[str] | None = 'l2m3n4o5p6q7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'artifact',
        sa.Column('id', Uuid(), primary_key=True),
        sa.Column('application_id', Uuid(),
                  sa.ForeignKey('application.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('code', sa.Text(), nullable=False),
        sa.Column('filename', sa.Text(), nullable=False),
        sa.Column('stored_path', sa.Text(), nullable=False),
        sa.Column('mime_type', sa.Text(), nullable=True),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('download_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_artifact_code', 'artifact', ['code'], unique=True)
    op.create_index('ix_artifact_application_id', 'artifact', ['application_id'])


def downgrade() -> None:
    op.drop_index('ix_artifact_application_id', table_name='artifact')
    op.drop_index('ix_artifact_code', table_name='artifact')
    op.drop_table('artifact')
