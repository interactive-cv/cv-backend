"""rename cover_letter_md to cover_letter

Revision ID: a1b2c3d4e5f6
Revises: 97f205d16183
Create Date: 2026-07-02 12:00:00.000000

Cover letter теперь хранится как плейн-текст (для копипаста в Telegram/email),
а не как markdown. Колонка переименована: cover_letter_md → cover_letter.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '97f205d16183'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # RENAME COLUMN работает и в PostgreSQL, и в SQLite (3.25+, 2018).
    # Без потери данных: колонка просто меняет имя, содержимое сохраняется.
    op.alter_column(
        'application',
        'cover_letter_md',
        new_column_name='cover_letter',
        existing_type=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        'application',
        'cover_letter',
        new_column_name='cover_letter_md',
        existing_type=sa.Text(),
        existing_nullable=True,
    )
