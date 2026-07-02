"""add interview table

Revision ID: 97f205d16183
Revises: 27b21766a2f2
Create Date: 2026-07-02 07:41:45.210558

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '97f205d16183'
down_revision: Union[str, Sequence[str], None] = '27b21766a2f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "interview",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("application_id", sa.Uuid, sa.ForeignKey("application.id"), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes_before", sa.Text, nullable=True),
        sa.Column("notes_after", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("interview")
