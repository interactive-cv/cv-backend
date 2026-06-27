"""initial schema

Revision ID: 78d31e7951d7
Revises:
Create Date: 2026-06-27 23:41:25.883201

Создаёт 5 таблиц: master_cv, cv_variant, short_link, link_hit, project.
JSON-колонки — нативный PostgreSQL JSONB (по спеке §6).
UUID PK — нативный PostgreSQL UUID.
Миграция выполняется на PostgreSQL (через Alembic); тесты моделей идут на SQLite через кросс-БД TypeDecorator в ORM (app.db.JSONB).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "78d31e7951d7"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # master_cv — единый источник правды (одна строка, id=1)
    op.create_table(
        "master_cv",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("contacts", JSONB, nullable=False),
        sa.Column("skills_core", JSONB, nullable=False, server_default="{}"),
        sa.Column("skills_familiar", JSONB, nullable=False, server_default="{}"),
        sa.Column("languages", JSONB, nullable=False, server_default="{}"),
        sa.Column("format", JSONB, nullable=False, server_default="{}"),
        sa.Column("full_markdown", sa.Text, nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # cv_variant — адаптированный вариант CV под вакансию
    op.create_table(
        "cv_variant",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("master_cv_id", sa.Integer, sa.ForeignKey("master_cv.id"), nullable=False),
        sa.Column("slug", sa.Text, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("company", sa.Text, nullable=True),
        sa.Column("content_markdown", sa.Text, nullable=False),
        sa.Column("vacancy_text", sa.Text, nullable=True),
        sa.Column(
            "status",
            sa.Enum("draft", "active", "archived", name="cvvariantstatus"),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_cv_variant_slug", "cv_variant", ["slug"], unique=True)

    # short_link — короткая ссылка с TTL и лимитом кликов
    op.create_table(
        "short_link",
        sa.Column("code", sa.Text, primary_key=True),
        sa.Column("cv_variant_id", sa.Uuid, sa.ForeignKey("cv_variant.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_hits", sa.Integer, nullable=True),
        sa.Column("hit_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # link_hit — аналитика переходов (ip_hash, не сырой IP)
    op.create_table(
        "link_hit",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("short_link_code", sa.Text, sa.ForeignKey("short_link.code"), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("referrer", sa.Text, nullable=True),
        sa.Column("ua", sa.Text, nullable=True),
        sa.Column("ip_hash", sa.Text, nullable=True),
    )

    # project — для графа знаний/таймлайна и RAG-контекста
    op.create_table(
        "project",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("period", sa.Text, nullable=False),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column("tags", JSONB, nullable=False, server_default="[]"),
        sa.Column("short_desc", sa.Text, nullable=False),
        sa.Column("long_desc", sa.Text, nullable=True),
        sa.Column("stack", JSONB, nullable=False, server_default="[]"),
        sa.Column("metrics", JSONB, nullable=False, server_default="{}"),
        sa.Column("order_idx", sa.Integer, nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("project")
    op.drop_table("link_hit")
    op.drop_table("short_link")
    op.drop_index("ix_cv_variant_slug", table_name="cv_variant")
    op.drop_table("cv_variant")
    op.drop_table("master_cv")
    op.execute("DROP TYPE IF EXISTS cvvariantstatus")
