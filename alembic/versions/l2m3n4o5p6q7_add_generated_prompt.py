"""add generated_prompt to application

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-07-12 12:00:00.000000

Application.generated_prompt — snapshot отрендеренного промпта,
который породил CV/cover letter. Для воспроизводимости и отладки.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'l2m3n4o5p6q7'
down_revision: Union[str, Sequence[str], None] = 'k1l2m3n4o5p6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('application', sa.Column('generated_prompt', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('application', 'generated_prompt')
