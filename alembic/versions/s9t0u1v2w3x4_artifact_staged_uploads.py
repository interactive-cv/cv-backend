"""artifact.application_id nullable (staged uploads)

Revision ID: s9t0u1v2w3x4
Revises: r8s9t0u1v2w3
Create Date: 2026-09-18 10:00:00.000000

Единое хранилище файлов: артефакты могут существовать до создания заявки
(application_id NULL) — загружаются на первом экране нового отклика,
привязываются при сохранении заявки.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 's9t0u1v2w3x4'
down_revision: str | Sequence[str] | None = 'r8s9t0u1v2w3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        'artifact', 'application_id',
        existing_type=sa.Uuid(), nullable=True,
    )


def downgrade() -> None:
    # Свисающих staged при downgrade быть не должно
    op.execute("DELETE FROM artifact WHERE application_id IS NULL")
    op.alter_column(
        'artifact', 'application_id',
        existing_type=sa.Uuid(), nullable=False,
    )
