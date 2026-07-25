"""add links to project

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-07-05 18:00:00.000000

Project.links — список ссылок [{label, url}] для модального окна проекта.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = 'h8i9j0k1l2m3'
down_revision: str | Sequence[str] | None = 'g7h8i9j0k1l2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('project', sa.Column('links', JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column('project', 'links')
