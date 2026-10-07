"""artifact.extracted_text (контекст LLM из файлов заявки)

Revision ID: t0u1v2w3x4y5
Revises: s9t0u1v2w3x4
Create Date: 2026-09-23 20:00:00.000000

Текст артефактов (pdf/docx/txt) извлекается при загрузке или on-demand
и подмешивается в контекст ассистента переговоров.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 't0u1v2w3x4y5'
down_revision: str | Sequence[str] | None = 's9t0u1v2w3x4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('artifact', sa.Column('extracted_text', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('artifact', 'extracted_text')
