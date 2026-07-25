"""add contest kind + prompt_generate_contest

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-07-11 12:00:00.000000

1. Расширение enum applicationkind: добавлено значение 'contest'.
2. Заполнение config_text.prompt_generate_contest дефолтным промптом,
   если запись отсутствует (для уже развёрнутых инстансов, где seed
   не создаст новый ключ автоматически).
"""
from collections.abc import Sequence

from sqlalchemy import text as sa_text

from alembic import op

revision: str = 'k1l2m3n4o5p6'
down_revision: str | Sequence[str] | None = 'j0k1l2m3n4o5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Добавляем 'contest' в enum.
    #    ALTER TYPE ... ADD VALUE не может быть внутри транзакции в старых
    #    PostgreSQL — alembic выставляет autocommit для таких операций.
    op.execute("ALTER TYPE applicationkind ADD VALUE IF NOT EXISTS 'contest'")

    # 2. Если config_text уже заполнен (не fresh install), создаём запись
    #    prompt_generate_contest с дефолтным промптом — чтобы ключ появился
    #    на уже развёрнутых инстансах без ручного seed.
    bind = op.get_bind()
    exists = bind.execute(
        sa_text("SELECT 1 FROM config_text WHERE key = 'prompt_generate_contest'")
    ).scalar()
    if not exists:
        from app.seed_defaults import DEFAULT_PROMPT_GENERATE_CONTEST

        bind.execute(
            sa_text(
                "INSERT INTO config_text (key, value) "
                "VALUES (:key, :value)"
            ),
            {"key": "prompt_generate_contest", "value": DEFAULT_PROMPT_GENERATE_CONTEST},
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa_text("DELETE FROM config_text WHERE key = 'prompt_generate_contest'")
    )
    # Удаление значения из enum в PostgreSQL невозможно напрямую.
    # Оставляем 'contest' в типе — это безвредно.
